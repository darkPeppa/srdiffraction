"""Конвейер восстановления по всему архиву, QA-панели и итоговый отчёт по интерферометрии."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml
from scipy import ndimage

from liga_common.io import dump_json
from liga_common.paths import CONFIG
from plotting.style import plt, save

from . import fringe_trace as ft
from .archive_inventory import file_id, list_images
from .height_reconstruct import depth_branches, phase_to_height
from .lateral_calibration import from_config
from .morphology import METRIC_DEFINITIONS, profile_metrics
from .phase_demodulate import demodulate, find_carrier
from .phase_unwrap import residues, unwrap_masked
from .preprocess import detect_panel, flatten_illumination, load_rgb, saturation_mask, to_intensity

PROCESSING_VERSION = "interferometry-1.0"


def _cfg():
    return yaml.safe_load((CONFIG / "interferometry.yaml").read_text(encoding="utf-8"))


def _val(v):
    return v.get("value") if isinstance(v, dict) else v


def process_image(path: Path, rel: str, roi: dict | None, out: Path, cfg: dict) -> dict:
    H = float(_val(cfg["calibration"]["height_per_fringe_um"]))
    pc = cfg["processing"]
    res = {"file": rel, "file_id": file_id(rel), "processing_version": PROCESSING_VERSION,
           "roi_source": "operator" if roi else "auto", "status": None, "notes": []}
    rgb = load_rgb(path)
    panel = None
    if roi:
        pan = [r for r in roi.get("rois", []) if r["label"] == "good_fringes"]
        if pan:
            r = max(pan, key=lambda r: (r["x1"] - r["x0"]) * (r["y1"] - r["y0"]))
            panel = (r["x0"], r["y0"], r["x1"], r["y1"])
    if panel is None:
        p = detect_panel(rgb, pc["panel_detection"]["green_minus_blue"], pc["panel_detection"]["min_area_fraction"],
                         pc["panel_detection"]["min_extent"])
        if p is None:
            res.update(status="needs_manual_roi", reason="панель живого изображения не найдена автоматически — "
                                                         "задайте ROI good_fringes в annotate-roi")
            return res
        panel = (p.x0, p.y0, p.x1, p.y1)
    x0, y0, x1, y1 = panel
    res["crop_in_original_px"] = {"x0": int(x0), "y0": int(y0), "x1": int(x1), "y1": int(y1)}
    crop = rgb[y0:y1, x0:x1]
    I = to_intensity(crop)
    In, env = flatten_illumination(I)
    sat = saturation_mask(crop)
    car = find_carrier(In)
    res["carrier"] = {"period_px": car.period_px, "angle_deg": car.angle_deg, "snr": car.snr}
    if not (3 <= car.period_px <= min(In.shape) / 4) or car.snr < 6:
        res.update(status="not_processable", reason=f"нет регулярной несущей полос (период {car.period_px:.1f} пкс, "
                                                    f"SNR {car.snr:.1f})")
        return res
    phase, mod, _ = demodulate(In, car, pc["fourier"]["sideband_halfwidth_frac"])
    # порог качества: абсолютный и относительный (утечка боковой полосы в области без полос)
    valid = (mod > max(pc["fourier"]["min_modulation"], 0.4 * float(np.median(mod)))) & ~sat
    if roi:
        for r in roi.get("rois", []):
            if r["label"] == "exclude":
                valid[max(r["y0"] - y0, 0):max(r["y1"] - y0, 0), max(r["x0"] - x0, 0):max(r["x1"] - x0, 0)] = False
    phi, lab, nreg = unwrap_masked(phase, valid)
    res["valid_fraction"] = float(np.isfinite(phi).mean())
    res["n_unwrapped_regions"] = int(nreg)
    nres = int(np.abs(residues(phase)[valid[:-1, :-1] & valid[1:, 1:]]).sum())
    res["phase_residues"] = nres
    # опорная поверхность: ROI оператора «surface», иначе — крупнейшая область (допущение)
    ref = np.zeros_like(valid)
    if roi and any(r["label"] == "surface" for r in roi.get("rois", [])):
        for r in roi["rois"]:
            if r["label"] == "surface":
                ref[max(r["y0"] - y0, 0):max(r["y1"] - y0, 0), max(r["x0"] - x0, 0):max(r["x1"] - x0, 0)] = True
        ref &= np.isfinite(phi)
        res["reference"] = "operator surface ROI"
    else:
        if nreg:
            sizes = ndimage.sum(np.ones_like(lab), lab, index=np.arange(1, nreg + 1))
            ref = lab == (int(np.argmax(sizes)) + 1)
        res["reference"] = "auto: крупнейшая связная валидная область (assumption — может включать углубление)"
    h, coef = phase_to_height(phi, ref, H)
    res["phase_branch_status"] = ("single_connected_region" if nreg == 1 else
                                  f"ambiguous_integer_periods_between_{nreg}_regions")
    # Метод 1 и сравнение с методом 2 вдоль отслеженных полос
    Ih, rot = ft.rotate_to_horizontal(In, car.angle_deg)
    hr = ndimage.rotate(np.nan_to_num(h, nan=np.nan), -rot, reshape=False, order=0, mode="constant", cval=np.nan)
    ref_cols = slice(0, max(10, In.shape[1] // 7))
    tracks = ft.trace_fringes(Ih, car.period_px, ref_cols, pc["fringe_trace"]["min_prominence"])
    dh1 = ft.displacement_height(tracks, ref_cols, car.period_px, H)
    diffs = []
    for t, d in zip(tracks, dh1):
        for x in range(len(t)):
            if np.isfinite(t[x]) and np.isfinite(d[x]):
                yy = int(round(t[x]))
                if 0 <= yy < hr.shape[0] and np.isfinite(hr[yy, x]):
                    diffs.append(d[x] - (hr[yy, x] - np.nanmedian(hr[:, ref_cols])))
    diffs = np.array(diffs)
    if len(diffs) > 50:
        # разности определены с точностью до константы на полосу → сравниваем разброс
        spread = float(np.median(np.abs(diffs - np.median(diffs))) * 1.4826)
        res["method_agreement"] = {"n_points": int(len(diffs)), "robust_sigma_um": spread,
                                   "criterion_um": 0.1 * H, "agree": bool(spread < 0.1 * H)}
    else:
        res["method_agreement"] = {"n_points": int(len(diffs)), "agree": None,
                                   "note": "метод 1 не дал достаточно непрерывных полос"}
    res["n_traced_fringes"] = int(sum(np.isfinite(t).sum() > In.shape[1] // 2 for t in tracks))
    # Профили: несколько сечений вдоль нормали к полосам и поперёк (в пикселях)
    profiles = []
    nsec = pc["profiles"]["n_sections"]
    for axis in (0, 1):
        for k in range(nsec):
            frac = (k + 1) / (nsec + 1)
            if axis == 0:
                line = h[int(frac * h.shape[0]), :]
            else:
                line = h[:, int(frac * h.shape[1])]
            x = np.arange(len(line), dtype=float)
            mplus = profile_metrics(x, -line)
            mminus = profile_metrics(x, line)
            profiles.append({"section_id": f"{res['file_id']}_{'row' if axis == 0 else 'col'}{k}", "axis":
                             "row" if axis == 0 else "col", "position_frac": frac, "metrics_sign_plus": mplus,
                             "metrics_sign_minus": mminus, "h_um": np.where(np.isfinite(line), line, np.nan).tolist()})
    res["profiles"] = profiles
    depths = [p["metrics_sign_plus"].get("depth") for p in profiles if p["metrics_sign_plus"].get("valid")]
    if depths:
        d = float(np.median(depths))
        res["relative_depth_um"] = d
        res["depth_branches_um"] = depth_branches(d, H, 15.0).tolist()[:8] + ["…"]
    lat = from_config(cfg, roi)
    res["lateral_scale_status"] = lat.status
    res["lateral_um_per_px"] = lat.um_per_px
    res["calibration_source"] = {"height": "0.27 мкм/период (документ)", "lateral": lat.source}
    good = res["valid_fraction"] > 0.3 and car.snr > 10
    res["status"] = ("relative_profile_available" if good and nreg <= 3 else "needs_manual_roi")
    res["metrological"] = False
    res["metrological_blockers"] = ["горизонтальный масштаб не подтверждён"] * (lat.status != "verified") + \
        ["неизвестно целое число периодов между несвязными областями/через стенку"] * (nreg != 1) + \
        ["знак высоты не установлен"]
    qa_panel(rgb, panel, In, mod, phase, h, valid, tracks, rot, res, out / "qa" / res["file_id"])
    return res


def qa_panel(rgb, panel, In, mod, phase, h, valid, tracks, rot, res, path):
    x0, y0, x1, y1 = panel
    fig, axs = plt.subplots(2, 3, figsize=(12, 7.2))
    axs[0, 0].imshow(rgb.astype(np.uint8))
    axs[0, 0].add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec="#e34948", lw=1.5))
    axs[0, 0].set_title("исходный снимок + область обработки", fontsize=8)
    axs[0, 1].imshow(In, cmap="gray")
    Ih, _ = ft.rotate_to_horizontal(In, res["carrier"]["angle_deg"])
    axs[0, 1].set_title(f"нормированные полосы; период {res['carrier']['period_px']:.1f} пкс, "
                        f"угол {res['carrier']['angle_deg']:.0f}°", fontsize=8)
    axs[0, 2].imshow(Ih, cmap="gray")
    for t in tracks:
        if np.isfinite(t).sum() > 10:
            axs[0, 2].plot(np.arange(len(t)), t, lw=0.6, color="#eb6834")
    axs[0, 2].set_title("метод 1: отслеженные тёмные полосы (повёрнуто)", fontsize=8)
    axs[1, 0].imshow(np.where(valid, mod, np.nan), cmap="Blues", vmin=0, vmax=1)
    axs[1, 0].set_title(f"модуляция (маска качества), валидно {res['valid_fraction']:.0%}", fontsize=8)
    axs[1, 1].imshow(np.where(valid, phase, np.nan), cmap="twilight")
    axs[1, 1].set_title("метод 2: обёрнутая фаза рельефа", fontsize=8)
    im = axs[1, 2].imshow(h, cmap="Blues")
    fig.colorbar(im, ax=axs[1, 2], fraction=0.046, label="Δh, мкм (знак не установлен)")
    axs[1, 2].set_title(f"относительная высота; {res['phase_branch_status']}", fontsize=7)
    for a in axs.flat:
        a.set_xticks([])
        a.set_yticks([])
        a.grid(False)
    fig.suptitle(f"{res['file']} — статус: {res['status']}; масштаб X: {res['lateral_scale_status']}", fontsize=9)
    # Только PNG (PDF с растровыми панелями весит 1–2 МБ на кадр)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path.with_suffix(".png"), dpi=110, bbox_inches="tight")
    plt.close(fig)


def reconstruct_all(archive: Path, roi_dir: Path, out: Path, only=None) -> list[dict]:
    cfg = _cfg()
    results = []
    files = list_images(archive)
    for p in files:
        rel = p.relative_to(archive).as_posix()
        if only and rel not in only:
            continue
        roi = None
        rp = roi_dir / f"{file_id(rel)}.json"
        if rp.exists():
            roi = json.loads(rp.read_text(encoding="utf-8"))
        try:
            r = process_image(p, rel, roi, out, cfg)
        except Exception as e:  # noqa: BLE001 — фиксируем как непригодный, не скрываем
            r = {"file": rel, "file_id": file_id(rel), "status": "processing_error", "reason": repr(e)}
        results.append(r)
        print(f"  {rel:45s} {r['status']:28s} {r.get('reason', '')[:70]}")
    slim = [{k: v for k, v in r.items() if k != "profiles"} for r in results]
    dump_json(slim, out / "reconstruction_summary.json")
    dump_json(results, out / "reconstruction_full.json")
    # таблица профилей по схеме ТЗ (раздел К)
    reg = {}
    regp = out / "image_registry.json"
    if regp.exists():
        reg = {r["file"]: r for r in json.loads(regp.read_text(encoding="utf-8"))}
    import csv
    with open(out / "profiles_table.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file_id", "section_id", "folder", "candidate_config", "config_confidence", "candidate_aperture_um",
                    "aperture_confidence", "x_px", "x_um", "h_um", "depth_um", "depth_ci_low_um", "depth_ci_high_um",
                    "valid_mask", "phase_branch_status", "calibration_source", "processing_version", "operator_approval"])
        for r in results:
            rg = reg.get(r["file"], {})
            for p in r.get("profiles", []):
                for i, hv in enumerate(p["h_um"]):
                    ok = hv is not None and np.isfinite(hv)
                    w.writerow([r["file_id"], p["section_id"], rg.get("folder", ""), rg.get("candidate_config", "unknown"),
                                rg.get("config_confidence", "unknown"), "unknown", "unknown", i,
                                (i * r["lateral_um_per_px"]) if r.get("lateral_um_per_px") else "",
                                hv if ok else "", (-hv) if ok else "", "", "", int(ok), r.get("phase_branch_status", ""),
                                "height:0.27um/period; lateral:" + str(r.get("lateral_scale_status")),
                                PROCESSING_VERSION, "no"])
    return results


def build_report(out: Path) -> Path:
    summ = json.loads((out / "reconstruction_summary.json").read_text(encoding="utf-8")) \
        if (out / "reconstruction_summary.json").exists() else []
    inv = json.loads((out / "inventory_summary.json").read_text(encoding="utf-8")) \
        if (out / "inventory_summary.json").exists() else {}
    sup = json.loads((out / "supervisor_validation.json").read_text(encoding="utf-8")) \
        if (out / "supervisor_validation.json").exists() else []
    att = json.loads((out / "attribution.json").read_text(encoding="utf-8")) if (out / "attribution.json").exists() else []
    cnt = {}
    for r in summ:
        cnt[r["status"]] = cnt.get(r["status"], 0) + 1
    best = {}
    for r in summ:
        if r["status"] in ("relative_profile_available", "needs_manual_roi"):
            folder = r["file"].split("/")[0]
            q = r.get("valid_fraction", 0) * min(r.get("carrier", {}).get("snr", 0), 50)
            if folder not in best or q > best[folder][0]:
                best[folder] = (q, r)
    L = ["# Отчёт: независимая обработка интерферограмм ПММА", "",
         f"Версия обработки: {PROCESSING_VERSION}. Высотная калибровка: 0.27 мкм на период полос (двойной ход учтён).",
         "", "## Инвентаризация", "",
         f"- изображений: {inv.get('n_images')}; по папкам: {inv.get('by_folder')}; форматы: {inv.get('by_format')}",
         f"- пар BMP/JPG с одним именем: {inv.get('pairs')}; кандидатов в дубликаты (перцептивный хэш): "
         f"{inv.get('near_duplicate_candidates')}",
         f"- расхождений SHA-256 с предоставленным реестром: {len(inv.get('sha256_mismatch_vs_provided_registry', []))}",
         "", "## Статусы обработки (все изображения)", "", "| Статус | Кадров |", "|---|---|"]
    for k, v in sorted(cnt.items()):
        L.append(f"| {k} | {v} |")
    L += ["", "Определения: `relative_profile_available` — восстановлена относительная карта высот (с точностью до "
          "целого числа периодов между областями, по X — пиксели); `needs_manual_roi` — полосы найдены, но качество/"
          "связность требуют ручной разметки; `not_processable` — нет панели или регулярных полос.",
          "Метрологически достоверных (абсолютная глубина + калиброванный X) кадров: **0** — см. блокеры ниже.", "",
          "## Лучший кадр каждой папки (автоматический критерий: доля валидных пикселей × SNR несущей)", "",
          "| Папка | Кадр | Статус | Период, пкс | Валидно | Δh_отн (мод 0.27), мкм | Совпадение методов 1/2 |",
          "|---|---|---|---|---|---|---|"]
    for f, (_, r) in sorted(best.items()):
        ma = r.get("method_agreement", {})
        L.append(f"| {f} | {r['file']} | {r['status']} | {r['carrier']['period_px']:.1f} | {r['valid_fraction']:.0%} | "
                 f"{r.get('relative_depth_um', float('nan')):.3f} | {ma.get('agree')} (σ={ma.get('robust_sigma_um', float('nan')):.3f}) |")
    L += ["", "## Аппроксимации руководителя (формулы из DOCX)", "",
          "| Эксперимент | Отверстие | Формула | Вердикт | Причины |", "|---|---|---|---|---|"]
    for r in sup:
        L.append(f"| {r['experiment']} | {r.get('hole_um')} | {r.get('formula', '')} | {r['verdict']} | "
                 f"{'; '.join(r['reasons'])[:300]} |")
    L += ["", "## Атрибуция кадров", "",
          f"matched: {sum(a['status'] == 'matched' for a in att)}, unmatched: {sum(a['status'] == 'unmatched' for a in att)}. "
          "Без независимого масштаба и карты отверстий размер отверстия по снимку не определяется (числа в именах "
          "файлов не считаются метрологией).", "",
          "## Чего не хватает (по убыванию пользы)", "",
          "1. Горизонтальная калибровка микроскопа/камеры (мкм/пиксель): снимок эталона тем же объективом и камерой.",
          "2. Карта расположения и размеров отверстий на образцах + журнал сессии (какой кадр — какое отверстие).",
          "3. Оригинальные кадры камеры без скриншотного интерфейса (лучше BMP/RAW) и/или серия фазовых сдвигов.",
          "4. Описание MII-4 и программы MI4: режим, апертура, длина волны/светофильтр, смысл поля «Z координата».",
          "5. Подтверждение высотной калибровки 0.27 мкм/период и её погрешности; знак смещения полос для углубления.",
          "6. Толщина и режим магнетронного напыления Au на проявленный ПММА.",
          "7. Температура, перемешивание и точное время проявления в диэтиленгликольмонобутиловом эфире; калибровка R(D).",
          "", "## Определения метрик", ""] + [f"- **{k}**: {v}" for k, v in METRIC_DEFINITIONS.items()]
    p = out / "interferometry_report.md"
    p.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"  отчёт: {p}")
    return p

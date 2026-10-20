"""Атрибуция кадров ↔ экспериментальные конфигурации и отверстия (гипотезы с достоверностью).

Признаки: папка (вероятная конфигурация), измеренная ширина углубления (только при
подтверждённой горизонтальной калибровке), соседние элементы/последовательность кадров
(ручная разметка). Запрещено выбирать гипотезу по минимуму невязки с Geant4 или с
аппроксимацией руководителя, если затем тот же профиль используется для их проверки.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from liga_common.io import dump_json
from liga_common.paths import CONFIG

APERTURES = {"be_200": [20, 200, 300, 600], "carbon_475": [15, 129, 300, 600],
             "sapphire_contact": [20, 60, 105, 300, 600], "sapphire_280mm": [20, 60, 105, 300, 600]}


def hypotheses(record: dict, measured_width_um: float | None = None, width_tol_rel: float = 0.25) -> list[dict]:
    cfg = record.get("candidate_config", "unknown")
    if cfg not in APERTURES:
        return [{"candidate_config": "unknown", "candidate_aperture_um": "unknown", "confidence": "unknown",
                 "basis": "папка не сопоставлена с конфигурацией"}]
    out = []
    for a in APERTURES[cfg]:
        if measured_width_um is None:
            conf, basis = "ambiguous", "нет горизонтальной калибровки — размер отверстия не определяется по снимку"
        else:
            rel = abs(measured_width_um - a) / a
            conf = "probable" if rel < width_tol_rel else "unlikely"
            basis = f"ширина углубления {measured_width_um:.1f} мкм vs окно {a} мкм (|Δ|/a={rel:.2f}); " \
                    "размер углубления не обязан совпадать с окном Au"
        out.append({"candidate_config": cfg, "config_confidence": record.get("config_confidence", "unknown"),
                    "candidate_aperture_um": a, "aperture_confidence": conf, "basis": basis})
    return out


def assign_features(out: Path) -> list[dict]:
    reg = out / "image_registry.json"
    if not reg.exists():
        raise FileNotFoundError("сначала выполните inventory-interferograms")
    rows = json.loads(reg.read_text(encoding="utf-8"))
    manual = {}
    mpath = CONFIG / "interferometry_attribution.yaml"
    if mpath.exists():
        manual = yaml.safe_load(mpath.read_text(encoding="utf-8")) or {}
    rec_path = out / "reconstruction_summary.json"
    recon = {}
    if rec_path.exists():
        recon = {r["file"]: r for r in json.loads(rec_path.read_text(encoding="utf-8"))}
    res = []
    for r in rows:
        m = manual.get(r["file"], {})
        width = None
        rr = recon.get(r["file"], {})
        if rr.get("lateral_scale_status") == "verified" and rr.get("width_at_50_um"):
            width = rr["width_at_50_um"]
        hyp = hypotheses(r, width)
        if m.get("aperture_um"):
            hyp = [{"candidate_config": m.get("config", r["candidate_config"]), "candidate_aperture_um": m["aperture_um"],
                    "aperture_confidence": m.get("confidence", "probable"),
                    "basis": "ручная атрибуция оператора: " + m.get("basis", "(основание не указано)")}]
        status = "matched" if any(h.get("aperture_confidence") in ("confirmed", "probable") for h in hyp) else "unmatched"
        res.append({"file": r["file"], "file_id": r["file_id"], "folder": r["folder"], "status": status,
                    "hypotheses": hyp,
                    "missing_for_attribution": [] if status == "matched" else [
                        "горизонтальный масштаб мкм/пиксель (эталон/паспорт объектива)",
                        "карта расположения отверстий на образце", "связь кадра с позицией на маске (журнал сессии)"]})
    dump_json(res, out / "attribution.json")
    n_m = sum(x["status"] == "matched" for x in res)
    print(f"  атрибуция: matched={n_m}, unmatched={len(res) - n_m} (без калибровки и карты отверстий — unmatched)")
    # таблица для ручного сопоставления
    with open(out / "manual_attribution_template.yaml", "w", encoding="utf-8") as f:
        f.write("# Заполните для кадров, где сопоставление установлено НЕЗАВИСИМО (журнал, карта образца, метки).\n"
                "# Затем скопируйте в config/interferometry_attribution.yaml и выполните assign-mask-features.\n")
        for x in res:
            f.write(f'"{x["file"]}": {{config: null, aperture_um: null, confidence: null, basis: null}}\n')
    return res

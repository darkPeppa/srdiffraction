"""Инвентаризация архива интерферограмм: реестр, пары BMP/JPG, перцептивные хэши, контактные листы.

Исходные файлы только читаются. Thumbs.db исключаются. Похожие кадры отмечаются как
кандидаты-дубликаты, но НЕ объединяются автоматически.
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw

from liga_common.io import dump_json
from liga_common.paths import CONFIG

IMG_EXT = {".jpg", ".jpeg", ".bmp", ".png", ".tif", ".tiff"}


def list_images(archive: Path) -> list[Path]:
    return sorted(p for p in archive.rglob("*") if p.suffix.lower() in IMG_EXT and p.name.lower() != "thumbs.db")


def dhash(img: Image.Image, size: int = 16) -> int:
    """Разностный перцептивный хэш (size×size бит) по яркости."""
    g = np.asarray(img.convert("L").resize((size + 1, size), Image.BILINEAR), dtype=float)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def file_id(rel: str) -> str:
    return hashlib.sha1(rel.encode("utf-8")).hexdigest()[:10]


def run_inventory(archive: Path, out: Path) -> list[dict]:
    cfg = yaml.safe_load((CONFIG / "interferometry.yaml").read_text(encoding="utf-8"))
    folders = cfg.get("folders", {})
    files = list_images(archive)
    rows = []
    hashes = {}
    for p in files:
        rel = p.relative_to(archive).as_posix()
        data = p.read_bytes()
        img = Image.open(p)
        h = dhash(img)
        hashes[rel] = h
        folder = rel.split("/")[0]
        fmeta = folders.get(folder, {})
        rows.append({"file_id": file_id(rel), "file": rel, "folder": folder,
                     "folder_original_name": fmeta.get("original_name", folder),
                     "format": img.format, "width_px": img.size[0], "height_px": img.size[1], "bytes": len(data),
                     "sha256": hashlib.sha256(data).hexdigest(), "basename": p.stem, "dhash": f"{h:064x}",
                     "candidate_config": fmeta.get("candidate_config", "unknown"),
                     "config_confidence": fmeta.get("confidence", "unknown"),
                     "candidate_aperture_um": "unknown", "aperture_confidence": "unknown",
                     "attribution_basis": fmeta.get("basis", ""),
                     "pair_status": "", "pair_mean_abs_diff": None, "near_duplicates": []})
    # пары BMP/JPG с одним именем
    by_stem = {}
    for r in rows:
        by_stem.setdefault((r["folder"], r["basename"]), []).append(r)
    for (_, _), group in by_stem.items():
        fmts = {r["format"] for r in group}
        if len(group) > 1 and {"BMP", "JPEG"} <= fmts:
            jpg = next(r for r in group if r["format"] == "JPEG")
            bmp = next(r for r in group if r["format"] == "BMP")
            a = np.asarray(Image.open(archive / jpg["file"]).convert("RGB"), dtype=float)
            b = np.asarray(Image.open(archive / bmp["file"]).convert("RGB"), dtype=float)
            mad = float(np.abs(a - b).mean()) if a.shape == b.shape else None
            for r in group:
                r["pair_status"] = "same-stem JPG/BMP"
                r["pair_mean_abs_diff"] = mad
            # BMP без потерь — предпочтительный экземпляр, если содержимое совпадает (MAD мал)
            bmp["pair_preferred"] = True
            jpg["pair_preferred"] = False
        else:
            for r in group:
                r["pair_status"] = "no same-stem pair"
                r["pair_preferred"] = True
    # кандидаты-дубликаты по перцептивному хэшу (между разными файлами, не парами)
    keys = list(hashes)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            d = hamming(hashes[a], hashes[b])
            if d <= 12 and Path(a).stem != Path(b).stem:
                ra = next(r for r in rows if r["file"] == a)
                rb = next(r for r in rows if r["file"] == b)
                ra["near_duplicates"].append({"file": b, "hamming": d})
                rb["near_duplicates"].append({"file": a, "hamming": d})
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "image_registry.csv", "w", newline="", encoding="utf-8") as f:
        cols = [k for k in rows[0] if k not in ("near_duplicates",)] + ["near_duplicates"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            rr = dict(r)
            rr["near_duplicates"] = ";".join(f"{d['file']}({d['hamming']})" for d in r["near_duplicates"])
            w.writerow(rr)
    dump_json(rows, out / "image_registry.json")
    # сверка с предоставленным реестром (контрольные суммы)
    prov = archive / "registry_provided.csv"
    mism = []
    if prov.exists():
        with open(prov, encoding="utf-8-sig") as f:
            given = {Path(r["file"]).name + "|" + r["sha256"] for r in csv.DictReader(f)}
        mism = [r["file"] for r in rows if Path(r["file"]).name + "|" + r["sha256"] not in given]
    contact_sheets(archive, rows, out / "contact_sheets")
    summary = {"n_images": len(rows), "by_folder": {}, "by_format": {}, "pairs": sum(r["pair_status"].startswith("same")
                                                                                       for r in rows) // 2,
               "near_duplicate_candidates": sum(len(r["near_duplicates"]) for r in rows) // 2,
               "sha256_mismatch_vs_provided_registry": mism}
    for r in rows:
        summary["by_folder"][r["folder"]] = summary["by_folder"].get(r["folder"], 0) + 1
        summary["by_format"][r["format"]] = summary["by_format"].get(r["format"], 0) + 1
    dump_json(summary, out / "inventory_summary.json")
    print(f"  изображений: {len(rows)} {summary['by_folder']} {summary['by_format']}; пар BMP/JPG: {summary['pairs']}; "
          f"кандидатов-дубликатов: {summary['near_duplicate_candidates']}; расхождений SHA-256 с реестром: {len(mism)}")
    return rows


def contact_sheets(archive: Path, rows: list[dict], out: Path, thumb=(288, 216), cols=4) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for folder in sorted({r["folder"] for r in rows}):
        rr = [r for r in rows if r["folder"] == folder]
        nrow = int(np.ceil(len(rr) / cols))
        sheet = Image.new("RGB", (cols * thumb[0], nrow * (thumb[1] + 18)), "white")
        d = ImageDraw.Draw(sheet)
        for i, r in enumerate(rr):
            im = Image.open(archive / r["file"]).convert("RGB").resize(thumb)
            x, y = (i % cols) * thumb[0], (i // cols) * (thumb[1] + 18)
            sheet.paste(im, (x, y + 18))
            d.text((x + 3, y + 3), f"{r['basename']} [{r['format']}] {r['file_id']}", fill=(0, 0, 0))
        sheet.save(out / f"{folder}.jpg", quality=88)

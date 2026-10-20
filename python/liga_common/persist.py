"""Сохранение результатов в results_persist/ (отслеживается git) — по флагу --persist.

Каталог results/ остаётся рабочим (игнорируется git). При --persist результаты команды
копируются в results_persist/<YYYY-MM-DD_HH-MM-SS_UTC>_<метка>/ с сохранением структуры
относительно results/ и манифестом MANIFEST.json (команда, коммит, файлы, SHA-256, пропуски).

Режимы:
  лёгкий (--persist)        — след прогона и отчёты: JSON (конфигурации, run_info, сводки), Markdown,
                              CSV, логи, PNG. Большие CSV/JSON (> 5 МБ) сжимаются gzip.
  тяжёлый (--persist-heavy) — дополнительно HDF5-карты дозы, PDF и QA-панели интерферограмм.
Никогда не копируются: фазовое пространство этапа 1 (*.bin; воспроизводимо тем же зерном),
дампы первичных частиц валидации генератора (prim_t*.csv), таблицы источника (source_table.csv —
пересоздаются из конфигурации).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .paths import REPO, RESULTS

PERSIST = REPO / "results_persist"

LIGHT_EXT = {".json", ".md", ".csv", ".txt", ".log", ".png", ".yaml", ".mac"}
HEAVY_EXT = {".h5", ".pdf"}
GZIP_OVER = 5 * 1024 * 1024          # сжимать текстовые файлы больше 5 МБ
MAX_FILE = 90 * 1024 * 1024          # GitHub не принимает файлы > 100 МБ


def _never(rel: str) -> str | None:
    name = rel.rsplit("/", 1)[-1]
    if name.endswith(".bin"):
        return "фазовое пространство этапа 1 (воспроизводимо тем же зерном)"
    if re.fullmatch(r"prim_t\d+\.csv", name):
        return "дамп первичных частиц валидации генератора"
    if name == "source_table.csv":
        return "таблица источника (пересоздаётся из конфигурации)"
    return None


def _git_commit() -> str:
    import os
    if os.environ.get("LIGA_GIT_COMMIT"):  # передаётся с хоста run.sh/run.ps1 (в контейнере git нет)
        return os.environ["LIGA_GIT_COMMIT"]
    try:
        out = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True,
                             text=True, timeout=10)
        dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True, timeout=10).stdout.strip()
        return out.stdout.strip() + ("+dirty" if dirty else "") if out.returncode == 0 else "unknown"
    except Exception:  # noqa: BLE001 — в контейнере git может отсутствовать
        return "unknown"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def persist(paths: list[Path], label: str, heavy: bool = False, command: str = "", rc: int | None = None) -> Path:
    """Скопировать результаты (файлы/каталоги внутри results/) в новый снимок results_persist/."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S_UTC")
    safe = re.sub(r"[^\w.-]+", "_", label).strip("_") or "run"
    dest = PERSIST / f"{stamp}_{safe}"
    dest.mkdir(parents=True, exist_ok=False)
    copied, skipped = [], []
    files: list[Path] = []
    for p in paths:
        p = Path(p)
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files += [f for f in sorted(p.rglob("*")) if f.is_file()]
    seen = set()
    for f in files:
        try:
            rel = f.resolve().relative_to(RESULTS.resolve()).as_posix()
        except ValueError:
            rel = f.name
        if rel in seen:
            continue
        seen.add(rel)
        size = f.stat().st_size
        reason = _never(rel)
        ext = f.suffix.lower()
        in_qa = "/qa/" in f"/{rel}"
        if reason is None:
            if ext in HEAVY_EXT or in_qa:
                if not heavy:
                    reason = "тяжёлый файл (сохраняется только с --persist-heavy)"
            elif ext not in LIGHT_EXT:
                reason = f"тип {ext or '(без расширения)'} не сохраняется"
        if reason:
            skipped.append({"file": rel, "bytes": size, "reason": reason})
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if ext in {".csv", ".json", ".txt", ".log"} and size > GZIP_OVER:
            target = target.with_name(target.name + ".gz")
            with open(f, "rb") as src, gzip.open(target, "wb", compresslevel=6) as dst:
                shutil.copyfileobj(src, dst)
        else:
            shutil.copy2(f, target)
        tsize = target.stat().st_size
        if tsize > MAX_FILE:
            target.unlink()
            skipped.append({"file": rel, "bytes": size, "reason": "больше 90 МБ даже после сжатия (лимит GitHub)"})
            continue
        copied.append({"file": target.relative_to(dest).as_posix(), "source": rel, "bytes": tsize,
                       "sha256": _sha(target)})
    manifest = {
        "created_utc": stamp, "label": label, "mode": "heavy" if heavy else "light",
        "command": command or " ".join(sys.argv), "exit_code": rc, "git_commit": _git_commit(),
        "n_files": len(copied), "total_bytes": sum(c["bytes"] for c in copied),
        "files": copied, "skipped": skipped,
        "note": "Структура повторяет results/. Повтор расчёта: liga_sim <stage*/stage*.json> "
                "(тот же seed даёт тот же результат) либо ./run.sh с той же командой.",
    }
    (dest / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_index(dest, manifest)
    mb = manifest["total_bytes"] / 2 ** 20
    print(f"[liga] сохранено в {dest.relative_to(REPO)}: {len(copied)} файлов, {mb:.1f} МБ "
          f"(пропущено {len(skipped)}; см. MANIFEST.json)")
    return dest


def _write_index(dest: Path, m: dict) -> None:
    """Короткий README снимка: что внутри и где главные отчёты."""
    keys = [c["file"] for c in m["files"]]
    main = [k for k in keys if k.endswith((".md",)) or k.endswith("summary.json")][:40]
    lines = [f"# Снимок результатов: {m['label']}", "",
             f"- создан: {m['created_utc']}", f"- команда: `{m['command']}`", f"- код: `{m['git_commit']}`",
             f"- режим: {m['mode']}; файлов: {m['n_files']}; объём: {m['total_bytes'] / 2 ** 20:.1f} МБ", "",
             "## Главные отчёты", ""] + [f"- [{k}]({k})" for k in main] + [
             "", "Полный список файлов, контрольные суммы и пропущенные файлы — `MANIFEST.json`."]
    (dest / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

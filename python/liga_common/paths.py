"""Пути проекта. Внутри контейнера репозиторий смонтирован в /work."""
from __future__ import annotations

import os
from pathlib import Path

REPO = Path(os.environ.get("LIGA_REPO", Path(__file__).resolve().parents[2]))
CONFIG = REPO / "config"
DATA = REPO / "data"
RESULTS = Path(os.environ.get("LIGA_RESULTS", REPO / "results"))
LIGA_SIM = os.environ.get("LIGA_SIM", "liga_sim")
LIGA_UNIT_TESTS = os.environ.get("LIGA_UNIT_TESTS", "liga_unit_tests")


def ensure(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

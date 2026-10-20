import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))


def have_geant4() -> bool:
    return shutil.which(os.environ.get("LIGA_SIM", "liga_sim")) is not None


requires_geant4 = pytest.mark.skipif(not have_geant4(), reason="liga_sim недоступен (запуск вне Docker-образа)")

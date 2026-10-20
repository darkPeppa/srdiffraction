"""Короткие прогоны Geant4 (только в Docker-образе): баланс энергии и модульные тесты C++."""
import os
import subprocess

import h5py
import pytest

from liga_cli.runner import run_liga_sim
from liga_cli.model import load_experiment

from conftest import requires_geant4

pytestmark = [pytest.mark.geant4, requires_geant4]


def test_cpp_unit_tests():
    assert subprocess.call([os.environ.get("LIGA_UNIT_TESTS", "liga_unit_tests")]) == 0


def test_slab_energy_balance(tmp_path):
    exp = load_experiment("be_200")
    cfg = {"run": {"name": "t", "n_events": 20000, "seed": 3, "threads": 2, "output": str(tmp_path / "o.h5")},
           "physics": {"em": "livermore"},
           "world": {"material": "Vacuum", "half_xy_mm": 50, "half_z_mm": 5},
           "materials": exp.materials_json({"Ti", "Vacuum"}),
           "layers": [{"name": "S", "role": "other", "material": "Ti", "thickness_um": 5, "z_front_mm": 0,
                       "half_x_mm": 40, "half_y_mm": 40}],
           "scoring": {"slab_test": True, "slab_layer": "S", "grids": []},
           "source": {"mode": "pencil", "pencil_energy_keV": 8, "z_mm": -1}}
    run_liga_sim(cfg, tmp_path / "c.json", tmp_path / "l.txt")
    with h5py.File(tmp_path / "o.h5") as f:
        b = dict(f["balance"].attrs)
        acc = f["balance/edep_by_role_MeV"][:].sum() + b["e_escape_MeV"] + b["e_killed_stack_MeV"] + b["e_killed_plane_MeV"]
        assert abs(acc / b["e_incident_MeV"] - 1) < 1e-9
        assert f["slab"].attrs["primaries"] == 20000

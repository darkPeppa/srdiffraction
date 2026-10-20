"""Геометрия конфигураций (без Geant4) + проверка навигатором Geant4 (маркер geant4)."""
import json
import subprocess

import pytest

from liga_cli.model import EXPERIMENTS, load_experiment

from conftest import requires_geant4


@pytest.mark.parametrize("exp_id", EXPERIMENTS)
def test_stack_order_and_thickness(exp_id):
    exp = load_experiment(exp_id)
    s1, s2, plane = exp.stage_layers(min(exp.holes), 0.5)
    roles = [l.role for l in s2]
    # по схемам: (мембрана) → Au → Ti → каптон → ПММА
    assert roles[-4:] == ["absorber", "mask_support", "kapton", "pmma"]
    pm = s2[-1]
    assert pm.thickness_um == 15.0
    zs = sorted((l.z_front_mm, l.z_back_mm) for l in s1 + s2)
    for a, b in zip(zs, zs[1:]):
        assert b[0] >= a[1] - 1e-12                         # слои не перекрываются
    assert plane < s2[0].z_front_mm
    assert s1[0].role == "al_filter"


def test_titanium_membrane_is_separate_volume():
    exp = load_experiment("titanium_model")
    _, s2, _ = exp.stage_layers(20, 0.5)
    names = [l.name for l in s2]
    assert "TestMembrane_Ti" in names and "MaskSupport_Ti" in names


def test_remote_sapphire_in_stage1():
    exp = load_experiment("sapphire_280mm")
    s1, s2, plane = exp.stage_layers(20, 0.5)
    mem = [l for l in s1 if l.role == "test_membrane"][0]
    assert abs(mem.z_back_mm + 280.0) < 1e-9
    al = [l for l in s1 if l.role == "al_filter"][0]
    assert abs(mem.z_front_mm - al.z_back_mm - 200.0) < 1e-9


def test_hole_only_in_gold():
    exp = load_experiment("be_200")
    _, s2, _ = exp.stage_layers(200, 0.5)
    assert [l.role for l in s2 if l.hole_um] == ["absorber"]


def test_pmma_thickness_guard():
    with pytest.raises(ValueError):
        load_experiment("be_200", {"geometry": {"pmma_um": 1}}).mask_stack(20, 1, {})


@pytest.mark.geant4
@requires_geant4
def test_geant4_geometry_check(tmp_path):
    from liga_cli.validation import Validator
    v = Validator(tmp_path, quick=True)
    v.test_geometry()
    assert all(r["pass"] for r in v.results)

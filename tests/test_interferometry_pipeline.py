"""Инвентаризация, ROI-редактор, атрибуция на реальном архиве (без изменения исходников)."""
import json

from experimental_interferometry.archive_inventory import run_inventory
from experimental_interferometry.attribution import hypotheses
from experimental_interferometry.roi_editor import build_editor
from liga_common.paths import DATA

ARCH = DATA / "experimental_profiles" / "interferograms"


def test_inventory(tmp_path):
    rows = run_inventory(ARCH, tmp_path)
    assert len(rows) == 106                                 # 91 JPG + 15 BMP (Thumbs.db исключены)
    s = json.loads((tmp_path / "inventory_summary.json").read_text())
    assert s["by_format"].get("BMP") == 15 and s["by_format"].get("JPEG") == 91
    assert s["sha256_mismatch_vs_provided_registry"] == []
    assert (tmp_path / "contact_sheets" / "Be220mkm.jpg").exists()


def test_roi_editor(tmp_path):
    p = build_editor(ARCH, tmp_path)
    t = p.read_text(encoding="utf-8")
    assert "Сохранить JSON" in t and "Be220mkm/" in t


def test_attribution_without_calibration_is_ambiguous():
    h = hypotheses({"candidate_config": "be_200", "config_confidence": "probable"})
    assert {x["candidate_aperture_um"] for x in h} == {20, 200, 300, 600}
    assert all(x["aperture_confidence"] == "ambiguous" for x in h)

"""Анализ: ширина перехода, слияние ячеек, формулы из DOCX, модель проявления."""
import numpy as np
from scipy.special import erf

from analysis.dose import adaptive_merge, transition_width
from comparison import supervisor_profiles as sp
from comparison.docx_formulas import extract_all
from experimental_interferometry.development_forward import (lateral_profile, rate_sigmoid, vertical_depth)
from liga_common.paths import DATA


def test_transition_width_erf():
    n = np.linspace(-30, 30, 601)
    s = 2.0
    D = 10 + 990 * 0.5 * (1 - erf(n / (np.sqrt(2) * s)))
    w, *_ = transition_width(n, D, 1000, 10)
    assert abs(w - 2.5631 * s) < 0.02                    # 10–90 % для гауссова размытия = 2.563σ


def test_adaptive_merge_conserves_sums():
    rng = np.random.default_rng(1)
    n = np.r_[np.linspace(-20, -0.25, 80), np.linspace(0.25, 20, 80)]
    E, V, S2 = rng.random(160), np.ones(160), rng.random(160) * 0.1
    m = adaptive_merge(n, E, V, S2, 0.05, 5.0)
    assert np.isclose(m[1].sum(), E.sum()) and np.isclose(m[2].sum(), V.sum())
    assert not np.any((m[0][:-1] < 0) & (m[0][1:] < 0) & False)


def test_docx_formula_extraction():
    d = extract_all(DATA / "source_documents" / "masks_techzadania")
    be = {p["hole_um"]: p for p in d["be_200"]["profiles"]}
    assert be[20.0]["K1"] == 100 and be[20.0]["K2"] == 50 and be[20.0]["offset_d"] == 32
    assert not be[600.0]["formula_present"]                 # в таблице нет формулы
    s280 = {p["hole_um"]: p for p in d["sapphire_280mm"]["profiles"]}
    assert s280[20.0]["K1"] == 99 and s280[20.0]["K2"] == 81 and s280[105.0]["sign"] == -1
    assert any("image4.wmf" in w for w in d["sapphire_contact"]["warnings"])


def test_supervisor_width_formula():
    p = {"formula_present": True, "K1": 100, "K2": 50, "c": 26, "a": 5, "b": 7, "scale": 1.893, "denom": 100,
         "sign": 1, "offset_d": 32}
    d = sp.derived(p)
    n = np.linspace(d["edge_position_n0"] - 50, d["edge_position_n0"] + 50, 20001)
    h = sp.h_of_n(p, n)
    lo, hi = 32 - 3.5 + 0.1 * 7, 32 - 3.5 + 0.9 * 7
    xs = [n[np.argmin(np.abs(h - v))] for v in (lo, hi)]
    assert abs(abs(xs[1] - xs[0]) - d["width_10_90"]) < 0.01


def test_development_zero_rate_stops():
    D = np.zeros((5, 15))
    z = np.linspace(0, 15, 16)
    assert np.all(vertical_depth(D, z, lambda X: np.zeros_like(X), 60) == 0)


def test_development_monotonic_and_capped():
    z = np.linspace(0, 15, 16)
    D = np.tile(np.linspace(0, 2000, 41)[:, None], (1, 15))
    rate = lambda X: rate_sigmoid(X, 0.0, 0.5, 1000, 100)
    d = vertical_depth(D, z, rate, 60)
    assert np.all(np.diff(d) >= -1e-12) and d.max() <= 15.0 + 1e-9
    x = np.linspace(-10, 10, 41)
    dl, T = lateral_profile(D, x, z, rate, 60)
    assert dl.max() <= 15.0 + 1e-9

"""Этап 2/4: ослабление (NIST, правило смеси, пропускание)."""
import numpy as np

from material_attenuation.materials import (Material, _nist_table, fractions_from_formula, mu_rho_nist,
                                            transmission)


def test_nist_interpolation_exact_at_nodes():
    E, mu, _ = _nist_table("Be")
    m = Material("Be", 1.848, {"Be": 1.0})
    sel = (E > 1.0) & (E < 100)
    assert np.allclose(mu_rho_nist(m, E[sel]), mu[sel], rtol=1e-9)


def test_absorption_edge_jump():
    au = Material("Au", 19.32, {"Au": 1.0})
    below, above = mu_rho_nist(au, [11.918, 11.92])
    assert above / below > 2.0                              # L3-край золота


def test_mixture_rule_matches_nist_pmma_table():
    E, mu, _ = _nist_table("PMMA")
    pm = Material("PMMA", 1.19, fractions_from_formula({"C": 5, "H": 8, "O": 2}))
    sel = (E >= 3) & (E <= 80)
    assert np.max(np.abs(mu_rho_nist(pm, E[sel]) / mu[sel] - 1)) < 0.01


def test_beer_lambert():
    be = Material("Be", 1.848, {"Be": 1.0})
    t1 = transmission(be, 100, [10.0])[0]
    t2 = transmission(be, 200, [10.0])[0]
    assert abs(t2 - t1 ** 2) < 1e-12

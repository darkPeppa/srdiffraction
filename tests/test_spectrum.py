"""Этап 1: спектр СИ (критерии заданы заранее)."""
import numpy as np
import pytest

from synchrotron_spectrum.sr import (INTEGRAL_G1, G1, Source, angular_flux, flux_per_mrad, power_per_mrad_W, trapz)
from spectrum_export.tables import SpectrumGrid, build_joint_table

SRC = Source(2.0, 2.0, 100.0)


def test_critical_energy_and_gamma():
    assert abs(SRC.critical_energy_keV - 5.32) < 0.01
    assert abs(SRC.critical_wavelength_A - 2.33) < 0.01
    assert abs(SRC.gamma - 3914) < 1


def test_G1_known_values():
    assert abs(G1(1.0)[0] - 0.6514) < 2e-4               # табличное значение G1(1)
    y = np.logspace(-7, 2.5, 4000)
    assert abs(trapz(G1(y), y) / INTEGRAL_G1 - 1) < 1e-4


def test_power_normalization():
    E = np.linspace(0.005, 200, 40000)
    P = trapz(flux_per_mrad(SRC, E) * E * 1e3 * 1.602176634e-19, E)
    assert abs(P / power_per_mrad_W(SRC) - 1) < 2e-3
    assert abs(power_per_mrad_W(SRC) - 6.75) < 0.01       # (4/9)·α·γ·(I/e)·Ec, Вт/мрад при 100 мА


@pytest.mark.parametrize("E", [1.0, 5.3, 20.0])
def test_schwinger_integrates_to_G1(E):
    psi = np.linspace(-5, 5, 20001)
    assert abs(trapz(angular_flux(SRC, [E], psi)[0], psi) / flux_per_mrad(SRC, [E])[0] - 1) < 1e-4


def test_field_scaling():
    assert abs(Source(2, 3, 100).critical_energy_keV / SRC.critical_energy_keV - 1.5) < 1e-12


def test_table_binning_uses_cell_integrals():
    g = SpectrumGrid(1, 40, 0.5, 1.5, 0.05)
    t = build_joint_table(SRC, g)
    E = np.linspace(1, 40, 20000)
    ref = trapz(flux_per_mrad(SRC, E), E)
    assert abs(t.total.sum() / ref - 1) < 2e-3            # интеграл по ячейкам = интеграл функции


def test_polarization_sigma_dominates():
    t = build_joint_table(SRC, SpectrumGrid(1, 40, 1.0, 1.5, 0.05))
    assert 0.8 < t.sigma.sum() / t.total.sum() < 0.95     # ~7/8 для углово-интегрированного СИ

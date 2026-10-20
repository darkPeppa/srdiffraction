"""Нормировка потока и дозы; сверка с опорными числами диссертации."""
import numpy as np

from liga_cli.model import load_experiment
from spectrum_export.tables import SpectrumGrid, build_joint_table, scan_averaged_fluence_rate
from synchrotron_spectrum.report import _dose_rate_surface


def _tab(filters, psi_lim):
    exp = load_experiment("be_200")
    M = exp.materials
    return exp, build_joint_table(exp.src, SpectrumGrid(1, 80, 0.1, 1.5, 0.02),
                                  [(M[m], t) for m, t in filters], psi_limit_mrad=psi_lim)


def test_scan_average_formula():
    exp, t = _tab([("Be", 500.0)], 15.0 / 20.3)
    r = scan_averaged_fluence_rate(t, 20.3, 15.0)
    assert abs(r - t.total.sum() / 20.3 / 30.0) / r < 1e-12


def test_dissertation_exposure_time_scanning():
    """Табл. 3 диссертации: 3.5 кДж/см³ при сканировании ±20 мм, Be 500 мкм, 100 мА — 7′45″ (допуск 15 %)."""
    exp, t = _tab([("Be", 500.0)], 1.0)
    rate = _dose_rate_surface(t, exp.materials, 20.0, 20.0)
    assert abs(3500 / rate / 60 / 7.75 - 1) < 0.15


def test_dissertation_power_density():
    """Табл. 2: 3.1 Вт/см² в медианной плоскости после 500 мкм Be (допуск 10 %)."""
    exp, t = _tab([("Be", 500.0)], 0.05)
    ec = 0.5 * (t.e_edges[1:] + t.e_edges[:-1])
    j0 = int(np.searchsorted(t.psi_edges, 0.0, side="right") - 1)
    P = (t.total[:, j0] / np.diff(t.psi_edges)[j0] * ec * 1.602176634e-16).sum() / 4.0
    assert abs(P / 3.1 - 1) < 0.10

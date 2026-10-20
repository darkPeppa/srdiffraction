"""Перевод развёрнутой фазы в высоту и учёт неоднозначности целого числа периодов.

h − h_ref = H/(2π) · (φ_unwrapped − φ_ref),  H = 0.27 мкм на период (двойной ход учтён).
Опорная плоскость определяется устойчивой регрессией (итеративное отбрасывание
выбросов) по неповреждённой поверхности вне углубления.
Знак (углубление → +/− фаза) не установлен документами: выдаются обе ветви.
Абсолютная разность высот между несвязными областями — неоднозначна на k·H.
"""
from __future__ import annotations

import numpy as np


def robust_plane(z: np.ndarray, mask: np.ndarray, iters: int = 5, k: float = 2.5):
    """Плоскость a + b·x + c·y по пикселям mask с отбрасыванием выбросов (|r| > k·MAD)."""
    yy, xx = np.nonzero(mask & np.isfinite(z))
    if len(xx) < 10:
        return np.zeros(3), np.zeros_like(z)
    v = z[yy, xx]
    sel = np.ones(len(v), bool)
    coef = np.zeros(3)
    for _ in range(iters):
        A = np.c_[np.ones(sel.sum()), xx[sel], yy[sel]]
        coef, *_ = np.linalg.lstsq(A, v[sel], rcond=None)
        r = v - (coef[0] + coef[1] * xx + coef[2] * yy)
        mad = np.median(np.abs(r[sel] - np.median(r[sel]))) * 1.4826 + 1e-12
        sel = np.abs(r) < k * mad
    Y, X = np.mgrid[0:z.shape[0], 0:z.shape[1]]
    return coef, coef[0] + coef[1] * X + coef[2] * Y


def phase_to_height(phi_unw: np.ndarray, ref_mask: np.ndarray, height_per_fringe_um: float):
    coef, plane = robust_plane(phi_unw, ref_mask)
    h = (phi_unw - plane) * height_per_fringe_um / (2 * np.pi)
    return h, coef


def depth_branches(fractional_depth_um: float, height_per_fringe_um: float, max_depth_um: float = 15.0):
    """Допустимые абсолютные глубины при неизвестном целом числе периодов: d = d_frac + k·H, 0 ≤ d ≤ max."""
    d0 = fractional_depth_um % height_per_fringe_um
    ks = np.arange(0, int(np.floor((max_depth_um - d0) / height_per_fringe_um)) + 1)
    return d0 + ks * height_per_fringe_um

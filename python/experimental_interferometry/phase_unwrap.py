"""Маскированное двумерное разворачивание фазы.

Используется алгоритм с сортировкой по надёжности (Herráez et al., 2002; реализация
scikit-image), который обходит пиксели в порядке убывания качества — вариант
quality-guided разворачивания. Невалидные пиксели (низкая модуляция, блики,
интерфейс) маскируются и остаются неопределёнными. Несвязные островки валидной
области разворачиваются независимо: их взаимный сдвиг неизвестен с точностью до
2π·k — это фиксируется в отчёте (phase_branch_status).
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage
from skimage.restoration import unwrap_phase


def unwrap_masked(phase: np.ndarray, valid: np.ndarray, min_region_px: int = 400):
    """Возвращает (развёрнутая фаза с NaN вне валидной области, метки связных областей, число областей)."""
    lab, n = ndimage.label(valid)
    sizes = ndimage.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1)) if n else []
    keep = np.zeros_like(valid)
    regions = 0
    for i, s in enumerate(sizes, start=1):
        if s >= min_region_px:
            keep |= lab == i
            regions += 1
    out = np.full(phase.shape, np.nan)
    if regions == 0:
        return out, lab * 0, 0
    ma = np.ma.masked_array(phase, mask=~keep)
    u = unwrap_phase(ma)
    out[keep] = np.asarray(u)[keep]
    lab2, n2 = ndimage.label(keep)
    return out, lab2, n2


def residues(phase: np.ndarray) -> np.ndarray:
    """Фазовые вычеты (точки разрыва): ненулевая циркуляция по элементарной петле 2×2."""
    def w(a):
        return (a + np.pi) % (2 * np.pi) - np.pi
    d1 = w(phase[:-1, 1:] - phase[:-1, :-1])
    d2 = w(phase[1:, 1:] - phase[:-1, 1:])
    d3 = w(phase[1:, :-1] - phase[1:, 1:])
    d4 = w(phase[:-1, :-1] - phase[1:, :-1])
    return np.round((d1 + d2 + d3 + d4) / (2 * np.pi)).astype(int)

"""Метод 1: отслеживание линий равной фазы (центров тёмных полос).

Изображение поворачивается так, чтобы полосы шли горизонтально. В каждом столбце
находятся минимумы яркости (субпиксельно, по параболе). Полосы отслеживаются по
столбцам от опорной области (край кадра вне структуры) с непрерывной нумерацией
порядка: минимум присоединяется к полосе, если он ближе p/2 к её положению в
предыдущем столбце. Смещение δs относительно линейной опорной аппроксимации,
делённое на локальный период p, даёт Δh = H·δs/p (H = 0.27 мкм на период).
Сравниваются только полосы одного порядка; потерянные полосы не «досчитываются».
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage, signal


def rotate_to_horizontal(I: np.ndarray, angle_deg: float) -> tuple[np.ndarray, float]:
    """Поворот так, чтобы нормаль к полосам была вертикальной (полосы — горизонтальные)."""
    rot = 90.0 - angle_deg
    return ndimage.rotate(I, -rot, reshape=False, order=1, mode="nearest"), rot


def column_minima(col: np.ndarray, min_distance: int, prominence: float) -> np.ndarray:
    pk, _ = signal.find_peaks(-col, distance=max(2, min_distance), prominence=prominence)
    out = []
    for p in pk:
        if 0 < p < len(col) - 1:
            a, b, c = col[p - 1], col[p], col[p + 1]
            den = a - 2 * b + c
            out.append(p + (0.5 * (a - c) / den if den != 0 else 0.0))
    return np.array(out)


def trace_fringes(Ih: np.ndarray, period_px: float, ref_cols: slice, prominence: float = 0.05):
    """Возвращает список полос: каждая — массив y(x) (NaN, где полоса потеряна)."""
    h, w = Ih.shape
    sm = ndimage.gaussian_filter1d(Ih, sigma=max(1.0, period_px / 8), axis=0)
    mins = [column_minima(sm[:, x], int(period_px * 0.6), prominence) for x in range(w)]
    x0 = ref_cols.start if ref_cols.start is not None else 0
    tracks = [[np.nan] * w for _ in range(len(mins[x0]))]
    for k, y in enumerate(mins[x0]):
        tracks[k][x0] = y
    for direction in (1, -1):
        last = {k: tracks[k][x0] for k in range(len(tracks))}
        rng = range(x0 + 1, w) if direction == 1 else range(x0 - 1, -1, -1)
        for x in rng:
            cand = mins[x]
            for k in list(last):
                if np.isnan(last[k]) or len(cand) == 0:
                    continue
                j = int(np.argmin(np.abs(cand - last[k])))
                if abs(cand[j] - last[k]) < 0.5 * period_px:
                    tracks[k][x] = cand[j]
                    last[k] = cand[j]
                else:
                    last[k] = np.nan  # полоса потеряна — дальше не продолжаем
    return [np.array(t) for t in tracks]


def displacement_height(tracks, ref_cols: slice, period_px: float, height_per_fringe_um: float):
    """Δh(x) для каждой полосы: (y − y_ref_line)/p · H. Опорная линия — МНК по ref_cols."""
    res = []
    for t in tracks:
        xs = np.arange(len(t))
        m = np.isfinite(t)
        mr = m & (xs >= (ref_cols.start or 0)) & (xs < (ref_cols.stop or len(t)))
        if mr.sum() < 5:
            res.append(np.full_like(t, np.nan))
            continue
        a, b = np.polyfit(xs[mr], t[mr], 1)
        res.append((t - (a * xs + b)) / period_px * height_per_fringe_um)
    return res

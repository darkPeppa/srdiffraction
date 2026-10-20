"""Морфометрия профилей: глубина, уровни 10/50/90 %, края, ширины, наклоны, асимметрия.

Все величины — в пикселях по горизонтали (пока нет независимой калибровки) и в мкм
по вертикали (с учётом неоднозначности целого числа периодов — см. height_reconstruct).
Определения метрик сохраняются вместе с результатами (METRIC_DEFINITIONS).
"""
from __future__ import annotations

import numpy as np

METRIC_DEFINITIONS = {
    "depth": "устойчивая глубина: медиана дна − медиана полки (верхние/нижние 20 % значений профиля)",
    "levels": "уровни 10/50/90 % от полки к дну",
    "edges": "положения пересечения уровня 50 % слева и справа (линейная интерполяция)",
    "width_at_level": "расстояние между левым и правым пересечением уровня",
    "transition_10_90": "ширина перехода 10–90 % на каждом краю",
    "wall_slope": "наклон стенки на интервале 25–75 % (Δh/Δx)",
    "asymmetry": "(переход_лев − переход_прав)/(среднее)",
}


def _crossings(x, y, level):
    xs = []
    for i in range(len(x) - 1):
        if np.isfinite(y[i]) and np.isfinite(y[i + 1]) and (y[i] - level) * (y[i + 1] - level) <= 0 and y[i] != y[i + 1]:
            xs.append(x[i] + (level - y[i]) * (x[i + 1] - x[i]) / (y[i + 1] - y[i]))
    return xs


def profile_metrics(x: np.ndarray, depth: np.ndarray) -> dict:
    """depth — глубина (положительная внутрь углубления); x — пиксели или мкм."""
    m = np.isfinite(depth)
    if m.sum() < 10:
        return {"valid": False, "reason": "мало валидных точек"}
    d = depth[m]
    xm = x[m]
    top = float(np.median(np.sort(d)[: max(3, len(d) // 5)]))
    bot = float(np.median(np.sort(d)[-max(3, len(d) // 5):]))
    D = bot - top
    if not np.isfinite(D) or D <= 0:
        return {"valid": False, "reason": "нет перепада"}
    out = {"valid": True, "depth": D, "top_level": top, "bottom_level": bot}
    lv = {p: top + p / 100 * D for p in (10, 25, 50, 75, 90)}
    c = {p: _crossings(xm, d, v) for p, v in lv.items()}
    if len(c[50]) >= 2:
        L, R = c[50][0], c[50][-1]
        out["edge_left"], out["edge_right"] = L, R
        out["width_at_50"] = R - L
        for p in (10, 90):
            if len(c[p]) >= 2:
                out[f"width_at_{p}"] = c[p][-1] - c[p][0]
        def trans(side):
            a = [v for v in c[10] if (v < out["edge_left"] + 1e-9 if side == "L" else v > out["edge_right"] - 1e-9)]
            b = [v for v in c[90] if (v < out["edge_right"] if side == "L" else v > out["edge_left"])]
            if not a or not b:
                return np.nan
            return abs((min(b) if side == "L" else max(b)) - (max(a) if side == "L" else min(a)))
        tl, tr = trans("L"), trans("R")
        out["transition_10_90_left"], out["transition_10_90_right"] = tl, tr
        if np.isfinite(tl) and np.isfinite(tr) and (tl + tr) > 0:
            out["asymmetry"] = (tl - tr) / (0.5 * (tl + tr))
        if c[25] and c[75]:
            out["wall_slope_left"] = 0.5 * D / max(abs(c[75][0] - c[25][0]), 1e-9)
            out["wall_slope_right"] = 0.5 * D / max(abs(c[75][-1] - c[25][-1]), 1e-9)
    elif len(c[50]) == 1:
        out["edge_single"] = c[50][0]
        if c[10] and c[90]:
            out["transition_10_90_single"] = abs(c[90][0] - c[10][0])
    out["area"] = float(np.trapz(np.clip(d - top, 0, None), xm)) if hasattr(np, "trapz") else None
    return out

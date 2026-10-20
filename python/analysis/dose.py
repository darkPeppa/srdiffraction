"""Производные величины: карты, профили поперёк края, доли рассеяния, ширина перехода."""
from __future__ import annotations

import numpy as np

from .io import Run


def depth_integrated(run: Run, grid: str = "map3d", e: np.ndarray | None = None, z_range=None):
    """D(x,y), усреднённая по глубине с учётом масс: ΣE/ΣV (Дж/см³)."""
    g = run.grids[grid]
    e = g.edep if e is None else e
    V = g.volumes_cm3()
    sel = slice(None)
    if z_range is not None:
        zc = g.zc
        sel = (zc >= z_range[0]) & (zc < z_range[1])
    return e[:, :, sel].sum(axis=2) * run.scale_J / V[:, :, sel].sum(axis=2)


def edge_profile(run: Run, hole_um: float, z_range=None, what: str = "total", index: int | None = None,
                 fold: bool = True, rebin_rel_err: float | None = None, max_width_um: float = 5.0):
    """Профиль дозы поперёк края по полосе edge_strip.

    Возвращает (n, D, sigma): n — расстояние от края отверстия, мкм
    (n < 0 — под отверстием, n > 0 — под золотом). При fold=True левая и правая
    половины совмещаются (симметрия квадратного отверстия), что удваивает статистику.
    """
    g = run.grids["edge_strip"]
    V = g.volumes_cm3()
    zc = g.zc
    zs = np.ones_like(zc, bool) if z_range is None else (zc >= z_range[0]) & (zc < z_range[1])
    if what == "total":
        e = g.edep
    elif what == "category":
        e = g.cat[index]
    else:
        e = g.feat[index]
    E = e[:, 0, zs].sum(axis=1)
    Vx = V[:, 0, zs].sum(axis=1)
    # погрешность (только для total) — по историям
    n_hist = run.n
    if what == "total":
        var = np.clip(g.edep_sq / n_hist - (g.edep / n_hist) ** 2, 0, None) / max(n_hist - 1, 1) * n_hist ** 2
        # Ячейки одной колонки по z могут быть коррелированы (один электрон — несколько ячеек),
        # поэтому берём консервативную верхнюю оценку σ_col = Σ_z σ_z (полная корреляция).
        S2 = np.sqrt(var[:, 0, zs]).sum(axis=1) ** 2
        if z_range is None and g.col_sq is not None:
            # точная дисперсия суммы по всей глубине (накоплена по историям в C++)
            colE = g.edep[:, 0, :].sum(axis=1)
            S2 = np.clip(g.col_sq[:, 0] / n_hist - (colE / n_hist) ** 2, 0, None) / max(n_hist - 1, 1) * n_hist ** 2
    else:
        S2 = np.zeros_like(E)
    xc = g.xc
    h2 = hole_um / 2
    if not fold:
        return xc, E * run.scale_J / Vx, np.sqrt(S2) * run.scale_J / Vx
    n = np.abs(xc) - h2
    # совмещаем по одинаковым |x| (сетка симметрична)
    key = np.round(n, 6)
    u = np.unique(key)
    Eu = np.array([E[key == k].sum() for k in u])
    Vu = np.array([Vx[key == k].sum() for k in u])
    Su = np.array([S2[key == k].sum() for k in u])
    if rebin_rel_err:
        # ширины исходных ячеек в координате n (для взвешенного центра)
        u, Eu, Vu, Su = adaptive_merge(u, Eu, Vu, Su, rebin_rel_err, max_width_um)
    return u, Eu * run.scale_J / Vu, np.sqrt(Su) * run.scale_J / Vu


def adaptive_merge(n, E, V, S2, rel_err: float, max_width_um: float):
    """Слияние соседних ячеек профиля до относительной погрешности ≤ rel_err.

    Не объединяет ячейки по разные стороны края (n = 0) и не создаёт ячеек
    шире max_width_um. Центр объединённой ячейки — среднее, взвешенное по объёму.
    """
    out = []
    i = 0
    N = len(n)
    while i < N:
        e = v = s2 = vn = 0.0
        j = i
        start = n[i]
        while j < N:
            if j > i and (np.sign(n[j]) != np.sign(start) and n[j] != 0):
                break
            if j > i and n[j] - start > max_width_um:
                break
            e += E[j]; v += V[j]; s2 += S2[j]; vn += V[j] * n[j]
            j += 1
            if e > 0 and np.sqrt(s2) / e <= rel_err:
                break
        out.append((vn / v, e, v, s2))
        i = j
    a = np.array(out)
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]


def plateau_levels(n, D, hole_um: float, inner_margin_um: float = 3.0, shadow_from_um: float = 20.0):
    """Уровни «открыто» (под отверстием вдали от края) и «тень» (под золотом вдали от края)."""
    h2 = hole_um / 2
    inner = (n <= -inner_margin_um) & (n >= -h2 + 0.0)
    if not inner.any():
        inner = n <= -min(inner_margin_um, h2 / 2)
    shadow = n >= shadow_from_um
    return float(np.mean(D[inner])) if inner.any() else np.nan, float(np.mean(D[shadow])) if shadow.any() else np.nan


def transition_width(n, D, d_open: float, d_shadow: float, lo: float = 0.1, hi: float = 0.9):
    """Ширина перехода lo–hi (по умолчанию 10–90%) от открытого уровня к уровню тени, мкм.

    Положения пересечений ищутся линейной интерполяцией по профилю, проходимому
    от центра отверстия наружу (первое пересечение каждого уровня).
    """
    if not (np.isfinite(d_open) and np.isfinite(d_shadow)) or d_open <= d_shadow:
        return np.nan, np.nan, np.nan
    order = np.argsort(n)
    n, D = n[order], D[order]
    def cross(level):
        # все пересечения уровня; берём ближайшее к краю (n = 0) — устойчиво к шуму плато
        xs = []
        for i in range(len(n) - 1):
            if (D[i] - level) * (D[i + 1] - level) <= 0 and D[i] != D[i + 1]:
                xs.append(n[i] + (level - D[i]) * (n[i + 1] - n[i]) / (D[i + 1] - D[i]))
        return min(xs, key=abs) if xs else np.nan
    l_hi = d_shadow + hi * (d_open - d_shadow)
    l_lo = d_shadow + lo * (d_open - d_shadow)
    n_hi, n_lo = cross(l_hi), cross(l_lo)
    return n_lo - n_hi, n_hi, n_lo


def region_masks(g, hole_um: float, margin_um: float = 5.0, shadow_from_um: float = 20.0):
    X, Y = np.meshgrid(g.xc, g.yc, indexing="ij")
    h2 = hole_um / 2
    m = min(margin_um, h2 / 2)
    open_ = (np.abs(X) < h2 - m) & (np.abs(Y) < h2 - m)
    shadow = (np.abs(X) > h2 + shadow_from_um) | (np.abs(Y) > h2 + shadow_from_um)
    return open_, shadow


def region_fraction(run: Run, hole_um: float, feature: str = "membrane_any_scatter"):
    """Доля энерговыделения историй с признаком в регионах open/shadow и по глубине."""
    g = run.grids["map3d"]
    fi = g.feat_names.index(feature)
    op, sh = region_masks(g, hole_um)
    out = {}
    for name, m in (("open", op), ("shadow", sh)):
        Et = g.edep[m].sum()
        Ef = g.feat[fi][m].sum()
        out[name] = float(Ef / Et) if Et > 0 else np.nan
        Etz = g.edep[m].sum(axis=0)
        Efz = g.feat[fi][m].sum(axis=0)
        out[name + "_by_depth"] = np.where(Etz > 0, Efz / np.where(Etz > 0, Etz, 1), np.nan).tolist()
    return out

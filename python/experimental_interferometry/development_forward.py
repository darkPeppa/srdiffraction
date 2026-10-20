"""Прямая модель проявления: доза D(x,z) → профиль растворённого слоя.

ВАЖНО: зависимость скорости растворения R(D) для сверхмолекулярного ПММА в
диэтиленгликольмонобутиловом эфире не откалибрована. Используются феноменологические
семейства (сигмоида, степенной закон) — параметры не являются физическими свойствами.

1) Вертикальная модель (без бокового травления): для каждого x находим глубину z, на
   которой t(z) = ∫₀ᶻ dz'/R(D(x,z')) достигает времени проявления t_dev (≤ 15 мкм).
2) Пространственная модель: время прихода фронта T(x,z) — решение уравнения эйконала
   |∇T| = 1/R(D) (алгоритм Дейкстры на 16-связной сетке, ошибка анизотропии < 3 %);
   растворено {T ≤ t_dev}. Боковое травление учитывается автоматически.
"""
from __future__ import annotations

import heapq
import math

import numpy as np


def rate_sigmoid(D, r_min: float, r_max: float, d50: float, width: float):
    """R(D) = r_min + (r_max − r_min)/(1 + exp(−(D − d50)/width)), мкм/с."""
    return r_min + (r_max - r_min) / (1.0 + np.exp(-(np.asarray(D) - d50) / width))


def rate_power(D, k: float, p: float, d0: float = 0.0):
    """R(D) = k·max(D − d0, 0)^p, мкм/с (D в Дж/см³)."""
    return k * np.clip(np.asarray(D) - d0, 0, None) ** p


def vertical_depth(D_xz: np.ndarray, z_edges_um: np.ndarray, rate_fn, t_dev_s: float) -> np.ndarray:
    """Глубина растворения для каждого столбца x (мкм). D_xz: [nx, nz]."""
    dz = np.diff(z_edges_um)
    R = rate_fn(D_xz)
    out = np.zeros(D_xz.shape[0])
    for i in range(D_xz.shape[0]):
        t = 0.0
        depth = 0.0
        for k in range(D_xz.shape[1]):
            r = R[i, k]
            if r <= 0:  # нулевая скорость — бесконечное время, растворение останавливается
                break
            dt = dz[k] / r
            if t + dt >= t_dev_s:
                depth += (t_dev_s - t) * r
                break
            t += dt
            depth += dz[k]
        out[i] = depth
    return out


_NEIGH = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1),
          (1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1)]


def arrival_time(R: np.ndarray, dx: float, dz: float) -> np.ndarray:
    """Время прихода фронта растворения от поверхности z=0 (строка 0) при скорости R[x,z]."""
    nx, nz = R.shape
    T = np.full((nx, nz), np.inf)
    h = []
    for i in range(nx):
        if R[i, 0] > 0:
            T[i, 0] = 0.5 * dz / R[i, 0]
            heapq.heappush(h, (T[i, 0], i, 0))
    while h:
        t, i, k = heapq.heappop(h)
        if t > T[i, k]:
            continue
        for di, dk in _NEIGH:
            a, b = i + di, k + dk
            if 0 <= a < nx and 0 <= b < nz and R[a, b] > 0:
                L = math.hypot(di * dx, dk * dz)
                tn = t + L * 0.5 * (1.0 / R[i, k] + 1.0 / R[a, b])
                if tn < T[a, b]:
                    T[a, b] = tn
                    heapq.heappush(h, (tn, a, b))
    return T


def lateral_profile(D_xz: np.ndarray, x_um: np.ndarray, z_edges_um: np.ndarray, rate_fn, t_dev_s: float):
    """Глубина растворения по x с учётом бокового проявления (по полю T ≤ t_dev)."""
    dx = float(np.median(np.diff(x_um)))
    dz = float(np.median(np.diff(z_edges_um)))
    T = arrival_time(rate_fn(D_xz), dx, dz)
    dissolved = T <= t_dev_s
    depth = np.zeros(len(x_um))
    for i in range(len(x_um)):
        ks = np.nonzero(dissolved[i])[0]
        depth[i] = (ks.max() + 1) * dz if len(ks) else 0.0
    return depth, T


def resample_uniform(x_c: np.ndarray, D: np.ndarray, step: float):
    """Перевод неравномерной сетки в равномерную (для эйконала) линейной интерполяцией по x."""
    xu = np.arange(x_c.min(), x_c.max() + 1e-9, step)
    return xu, np.vstack([np.interp(xu, x_c, D[:, k]) for k in range(D.shape[1])]).T

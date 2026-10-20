"""Метод 2: пространственное выделение боковой полосы (Фурье, Takeda) и карта качества.

Модель: I(x,y) = A + B·cos[2π(fx·x + fy·y) + φ_relief(x,y)].
Боковая полоса вокруг несущей (fx, fy) выделяется гауссовым окном, после обратного
преобразования несущая вычитается → обёрнутая фаза φ_relief ∈ (−π, π] и амплитуда
модуляции |B|. Работает, только если в кадре есть достаточно регулярная несущая.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Carrier:
    fx: float          # циклов на пиксель
    fy: float
    period_px: float
    angle_deg: float   # направление нормали к полосам
    snr: float         # пик несущей / медиана спектра вне DC


def find_carrier(I: np.ndarray, dc_radius_frac: float = 0.02) -> Carrier:
    h, w = I.shape
    win = np.outer(np.hanning(h), np.hanning(w))
    F = np.fft.fftshift(np.abs(np.fft.fft2((I - I.mean()) * win)))
    fy = np.fft.fftshift(np.fft.fftfreq(h))[:, None]
    fx = np.fft.fftshift(np.fft.fftfreq(w))[None, :]
    r = np.sqrt(fx ** 2 + fy ** 2)
    F2 = F.copy()
    F2[r < max(dc_radius_frac, 2.0 / min(h, w))] = 0
    F2[(fx < 0) | ((fx == 0) & (fy < 0))] = 0  # полуплоскость (симметрия спектра)
    iy, ix = np.unravel_index(np.argmax(F2), F2.shape)
    cfx, cfy = float(fx[0, ix]), float(fy[iy, 0])
    f = np.hypot(cfx, cfy)
    snr = float(F2[iy, ix] / (np.median(F2[F2 > 0]) + 1e-12))
    return Carrier(cfx, cfy, 1.0 / f if f > 0 else np.inf, float(np.degrees(np.arctan2(cfy, cfx))), snr)


def demodulate(I: np.ndarray, car: Carrier, halfwidth_frac: float = 0.5):
    """Возвращает (обёрнутая фаза рельефа, относительная модуляция, комплексный сигнал)."""
    h, w = I.shape
    F = np.fft.fft2(I - I.mean())
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    f0 = np.hypot(car.fx, car.fy)
    s = halfwidth_frac * f0
    G = np.exp(-((fx - car.fx) ** 2 + (fy - car.fy) ** 2) / (2 * s ** 2))
    c = np.fft.ifft2(F * G)
    yy, xx = np.mgrid[0:h, 0:w]
    c = c * np.exp(-2j * np.pi * (car.fx * xx + car.fy * yy))
    phase = np.angle(c)
    amp = np.abs(c)
    mod = 2 * amp / (np.abs(I - I.mean()).mean() * 2 + 1e-12)
    return phase, mod / (np.percentile(mod, 99) + 1e-12), c

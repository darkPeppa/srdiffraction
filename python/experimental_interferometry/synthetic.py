"""Синтетические интерферограммы для тестов (известный рельеф → полосы).

I = A(x,y)·[1 + V·cos(2π(fx·x + fy·y) + 2π·h(x,y)/H)] + шум,  H = 0.27 мкм на период.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image


def fringes(h_um: np.ndarray, period_px: float = 12.0, angle_deg: float = 90.0, H: float = 0.27,
            visibility: float = 0.8, illum_grad: float = 0.0, noise: float = 0.0, seed: int = 0) -> np.ndarray:
    ny, nx = h_um.shape
    yy, xx = np.mgrid[0:ny, 0:nx]
    f = 1.0 / period_px
    fx, fy = f * np.cos(np.radians(angle_deg)), f * np.sin(np.radians(angle_deg))
    A = 1.0 + illum_grad * (xx / nx - 0.5)
    I = A * (1 + visibility * np.cos(2 * np.pi * (fx * xx + fy * yy) + 2 * np.pi * h_um / H))
    if noise:
        I = I + np.random.default_rng(seed).normal(0, noise, I.shape)
    return I


def step(shape=(256, 256), height_um=0.135, x_edge=128, width_px=0.0):
    h = np.zeros(shape)
    x = np.arange(shape[1])
    prof = height_um / (1 + np.exp(-(x - x_edge) / width_px)) if width_px > 0 else height_um * (x >= x_edge)
    return h + prof[None, :]


def slope(shape=(256, 256), total_um=1.0):
    return np.tile(np.linspace(0, total_um, shape[1]), (shape[0], 1))


def jpeg_roundtrip(I: np.ndarray, quality: int = 50) -> np.ndarray:
    a = np.clip(I / I.max() * 255, 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(a).save(buf, format="JPEG", quality=quality)
    return np.asarray(Image.open(io.BytesIO(buf.getvalue())), dtype=float) / 255.0


def piecewise_slope(shape=(256, 256), total_um=0.81, x0=100, x1=200):
    x = np.arange(shape[1])
    prof = np.clip((x - x0) / (x1 - x0), 0, 1) * total_um
    return np.tile(prof, (shape[0], 1))


def recon(I: np.ndarray, H: float = 0.27, ref_cols: int = 40, min_mod: float = 0.05, ref_mask=None):
    """Восстановление методом 2 (для тестов): возвращает высоту и маску."""
    from .height_reconstruct import phase_to_height
    from .phase_demodulate import demodulate, find_carrier
    from .phase_unwrap import unwrap_masked
    from .preprocess import flatten_illumination
    In, _ = flatten_illumination(I, sigma=max(I.shape) / 8)
    car = find_carrier(In)
    ph, mod, _ = demodulate(In, car)
    valid = mod > max(min_mod, 0.4 * float(np.median(mod)))
    phi, lab, n = unwrap_masked(ph, valid)
    if ref_mask is None:
        ref = np.zeros_like(valid)
        ref[:, :ref_cols] = True
    else:
        ref = ref_mask.copy()
    ref &= np.isfinite(phi)
    h, _ = phase_to_height(phi, ref, H)
    return h, valid, car, n

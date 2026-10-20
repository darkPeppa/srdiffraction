"""Предобработка: поиск панели живого изображения интерферометра на скриншоте, вырезка, нормировка.

Кадры архива — скриншоты Windows (окна MII4/ScopePhoto, миниатюры «Кадр №1/№2», обои).
Панель интерферограммы — крупная почти прямоугольная область желто-зелёного цвета.
Координаты вырезки всегда сохраняются относительно исходного снимка.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from PIL import Image
from scipy import ndimage


@dataclass
class Panel:
    x0: int
    y0: int
    x1: int
    y1: int
    area_fraction: float
    extent: float
    method: str = "auto_color"

    def as_dict(self):
        return asdict(self)


def load_rgb(path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=float)


def detect_panel(rgb: np.ndarray, green_minus_blue: float = 25, min_area_fraction: float = 0.06,
                 min_extent: float = 0.80) -> Panel | None:
    """Панель — жёлто-зелёная область: B ≪ G, R ≈ 0.6–1.15·G (отличает от зелёных обоев, где R ≪ G)."""
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mask = (G - B > max(green_minus_blue, 40)) & (R > 0.62 * G) & (R < 1.15 * G) & (G > 50)
    mask = ndimage.binary_closing(mask, structure=np.ones((9, 9)), iterations=2)
    mask = ndimage.binary_opening(mask, structure=np.ones((5, 5)))
    lab, n = ndimage.label(mask)
    if n == 0:
        return None
    best = None
    H, W = mask.shape
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        comp = lab[sl] == i
        # обрезка строк/столбцов с низким заполнением (прилипшие элементы интерфейса)
        rows = np.nonzero(comp.mean(axis=1) > 0.6)[0]
        cols = np.nonzero(comp.mean(axis=0) > 0.6)[0]
        if len(rows) < 20 or len(cols) < 20:
            continue
        y0, y1 = sl[0].start + rows[0], sl[0].start + rows[-1] + 1
        x0, x1 = sl[1].start + cols[0], sl[1].start + cols[-1] + 1
        sub = lab[y0:y1, x0:x1] == i
        h, w = y1 - y0, x1 - x0
        extent = sub.mean()
        frac = h * w / (H * W)
        aspect = w / max(h, 1)
        if frac < min_area_fraction or extent < min_extent or not (0.6 < aspect < 2.2):
            continue
        if best is None or frac > best.area_fraction:
            best = Panel(int(x0), int(y0), int(x1), int(y1), float(frac), float(extent))
    if best is not None:
        m = 3  # отступ от рамки панели (края часто размыты/затемнены)
        best.x0 += m
        best.y0 += m
        best.x1 -= m
        best.y1 -= m
    return best


def to_intensity(rgb_crop: np.ndarray) -> np.ndarray:
    """Яркость полос. Для цветных (белый свет) полос используем сумму R+G (максимальный контраст на жёлто-зелёном)."""
    I = rgb_crop[..., 0] + rgb_crop[..., 1]
    return I / I.max() if I.max() > 0 else I


def flatten_illumination(I: np.ndarray, sigma: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Нормировка неоднородного освещения: (I − фон)/огибающая. Возвращает (нормированное, огибающая)."""
    if sigma is None:
        sigma = max(I.shape) / 25
    bg = ndimage.gaussian_filter(I, sigma)
    d = I - bg
    env = np.sqrt(ndimage.gaussian_filter(d ** 2, sigma)) + 1e-9
    return d / env, env / (bg + 1e-9)


def saturation_mask(rgb_crop: np.ndarray, hi: float = 250) -> np.ndarray:
    """Маска бликов/насыщения (любой канал ≥ hi)."""
    return (rgb_crop >= hi).any(axis=-1)

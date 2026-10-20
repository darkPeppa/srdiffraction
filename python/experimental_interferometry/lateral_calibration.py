"""Горизонтальная калибровка мкм/пиксель.

Независимого масштаба в архиве нет. Допустимые источники (в порядке приоритета):
снимок микрометрического эталона тем же объективом и камерой; паспортные данные
объектива/камеры MII-4 + TCAM3; достоверная программная шкала. ЗАПРЕЩЕНО получать
масштаб подбором к номинальному размеру отверстия (круговая проверка).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LateralScale:
    um_per_px: float | None
    source: str
    status: str  # verified | unverified

    @property
    def verified(self) -> bool:
        return self.status == "verified" and self.um_per_px is not None


def from_config(cfg: dict, roi: dict | None = None) -> LateralScale:
    """Масштаб из ROI-файла оператора (с указанием источника) или из config/interferometry.yaml."""
    if roi and roi.get("lateral_um_per_px") and roi.get("lateral_scale_source"):
        src = roi["lateral_scale_source"]
        if "aperture" in src.lower() or "отверст" in src.lower():
            return LateralScale(None, f"отклонено: масштаб по размеру отверстия ({src}) — круговая проверка",
                                "unverified")
        return LateralScale(float(roi["lateral_um_per_px"]), src, "verified")
    v = cfg.get("calibration", {}).get("lateral_um_per_px")
    if isinstance(v, dict):
        v = v.get("value")
    if v:
        return LateralScale(float(v), "config/interferometry.yaml", "verified")
    return LateralScale(None, "нет независимой калибровки", "unverified")

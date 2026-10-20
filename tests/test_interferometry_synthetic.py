"""Синтетические тесты восстановления рельефа (допуски заданы заранее, ТЗ раздел К)."""
import numpy as np
import pytest

from experimental_interferometry.height_reconstruct import depth_branches
from experimental_interferometry.lateral_calibration import from_config
from experimental_interferometry.synthetic import (fringes, jpeg_roundtrip, piecewise_slope, recon, step)

H = 0.27


def _step_val(h, x_edge=128, guard=30):
    """|Δh|: знак восстановленной высоты зависит от выбора сопряжённого пика несущей
    (направления наклона опорного зеркала) и по одному кадру не определяется."""
    return abs(np.nanmedian(h[:, x_edge + guard:-10]) - np.nanmedian(h[:, 40:x_edge - guard]))


def test_flat_tilted_fringes():
    h, *_ = recon(fringes(np.zeros((256, 256)), angle_deg=75))
    assert np.nanstd(h[20:-20, 20:-20]) < 0.005          # допуск 5 нм


def _mod(v, target):
    """Расстояние между значениями по модулю периода H (эквивалентность ветвей)."""
    d = (v - target) % H
    return min(d, H - d)


def test_step_half_period_pi():
    """Ступенька π (0.135 мкм): величина определяется по модулю H, знак/ветвь вырождены (+π ≡ −π)."""
    h, *_ = recon(fringes(step(height_um=0.135)))
    assert _mod(_step_val(h), 0.135) < 0.01              # допуск 10 нм


def test_step_small():
    h, *_ = recon(fringes(step(height_um=0.08)))
    assert abs(_step_val(h) - 0.08) < 0.01


def test_step_full_period_is_ambiguous():
    """Ступенька ровно 0.27 мкм (2π) по одному кадру неотличима от нуля: требуется ветвь k·H."""
    h, *_ = recon(fringes(step(height_um=0.27)))
    v = _step_val(h)
    assert abs(v) < 0.01 or abs(abs(v) - H) < 0.01
    br = depth_branches(abs(v), H, 15.0)
    assert np.isclose(br, 0.27, atol=0.011).any() and len(br) > 50   # ~56 допустимых ветвей до 15 мкм


def test_continuous_slope_several_periods():
    hh = piecewise_slope(total_um=0.81)                   # 3 периода на 100 пикселях
    h, *_ = recon(fringes(hh))
    assert abs(abs(np.nanmedian(h[:, 210:250]) - np.nanmedian(h[:, 10:90])) - 0.81) < 0.03


def test_nonuniform_illumination():
    h, *_ = recon(fringes(step(height_um=0.08), illum_grad=0.8))
    assert abs(_step_val(h) - 0.08) < 0.015


def test_noise_and_glare_tolerance():
    I = fringes(step(height_um=0.08), noise=0.15, seed=3)
    I[100:110, 60:70] = I.max()                           # блик
    h, *_ = recon(I)
    assert abs(_step_val(h) - 0.08) < 0.02


def test_jpeg_compression():
    h, *_ = recon(jpeg_roundtrip(fringes(step(height_um=0.08)), quality=50))
    assert abs(_step_val(h) - 0.08) < 0.02


def test_rotated_orientation_with_proper_reference():
    hh = step(height_um=0.08).T                           # ступенька вдоль y, полосы вертикальные
    ref = np.zeros(hh.shape, bool)
    ref[10:90, :] = True
    h, *_ = recon(fringes(hh, angle_deg=0), ref_mask=ref)
    assert abs(abs(np.nanmedian(h[170:240, :]) - np.nanmedian(h[20:90, :])) - 0.08) < 0.015


def test_sign_is_convention_dependent():
    """Один и тот же рельеф при сопряжённых несущих даёт противоположный знак — знак не выводится из кадра."""
    a, *_ = recon(fringes(step(height_um=0.08), angle_deg=0))
    b, *_ = recon(fringes(step(height_um=0.08), angle_deg=90))
    sa = np.nanmedian(a[:, 170:240]) - np.nanmedian(a[:, 20:90])
    sb = np.nanmedian(b[:, 170:240]) - np.nanmedian(b[:, 20:90])
    assert abs(abs(sa) - abs(sb)) < 0.01


def test_hole_in_fringes_and_contamination_masked():
    I = fringes(step(height_um=0.08))
    yy, xx = np.mgrid[0:256, 0:256]
    I[(yy - 60) ** 2 + (xx - 200) ** 2 < 15 ** 2] = 0.05  # загрязнение: нет полос
    h, valid, car, n = recon(I)
    assert not valid[60, 200]                              # область исключена маской
    assert abs(_step_val(h) - 0.08) < 0.02


def test_lateral_scale_from_aperture_is_rejected():
    s = from_config({"calibration": {"lateral_um_per_px": {"value": None}}},
                    {"lateral_um_per_px": 0.5, "lateral_scale_source": "подбор по размеру отверстия 300 мкм"})
    assert not s.verified and s.um_per_px is None


def test_lateral_scale_unverified_by_default():
    assert from_config({"calibration": {"lateral_um_per_px": {"value": None}}}).status == "unverified"

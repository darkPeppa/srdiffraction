"""Спектр синхротронного излучения поворотного магнита (основной полюс вигглера ВЭПП-3).

Стандартная теория излучения ультрарелятивистского электрона в однородном поле
(Швингер; Jackson, Classical Electrodynamics, гл. 14; X-ray Data Booklet, разд. 2.1;
формулы (1.1)–(1.3) диссертации Б.Г. Гольденберга).

Обозначения:
    γ  = E_e / (m_e c²)
    ρ  = E_e / (e c B)                         — радиус орбиты
    E_c = (3/2) ħ c γ³ / ρ                      — критическая энергия
    y  = E / E_c
    G1(y) = y ∫_y^∞ K_{5/3}(t) dt               — углово-интегрированный спектр
Число фотонов на единицу горизонтального угла θ и относительной ширины полосы:
    d²N/(dt dθ (dE/E)) = (√3 / 2π) α γ (I/e) G1(y)
Вертикальное распределение (X = γψ, ξ = (y/2)(1+X²)^{3/2}):
    d³N/(dt dθ dψ (dE/E)) = (3α / 4π²) γ² (I/e) y² (1+X²)² [K²_{2/3}(ξ) + X²/(1+X²) K²_{1/3}(ξ)]
Первое слагаемое — σ-поляризация (вектор E в плоскости орбиты, горизонтальный),
второе — π-поляризация (вертикальный).

Все функции возвращают значения в «практических» единицах:
фотоны / (с · мА · мрад_гориз · кэВ [· мрад_верт]).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import integrate, special

# np.trapezoid появился в NumPy 2.0; в образе Ubuntu 24.04 — NumPy 1.26.
trapz = getattr(np, "trapezoid", None) or np.trapz

# Физические константы (CODATA 2018)
ALPHA = 7.2973525693e-3
E_CHARGE = 1.602176634e-19       # Кл
ME_C2_MEV = 0.51099895000        # МэВ
HBAR_C_KEV_M = 1.973269804e-10   # ħc в кэВ·м
C_LIGHT = 299792458.0            # м/с
HC_KEV_ANGSTROM = 12.398419843   # hc в кэВ·Å


@dataclass(frozen=True)
class Source:
    electron_energy_GeV: float = 2.0
    field_T: float = 2.0
    current_mA: float = 100.0

    @property
    def gamma(self) -> float:
        return self.electron_energy_GeV * 1e3 / ME_C2_MEV

    @property
    def radius_m(self) -> float:
        # ρ = p/(eB) = E/(e c B) для β≈1
        return self.electron_energy_GeV * 1e9 / (C_LIGHT * self.field_T)

    @property
    def critical_energy_keV(self) -> float:
        return 1.5 * HBAR_C_KEV_M * self.gamma ** 3 / self.radius_m

    @property
    def critical_wavelength_A(self) -> float:
        return HC_KEV_ANGSTROM / self.critical_energy_keV

    @property
    def natural_opening_angle_mrad(self) -> float:
        """1/γ — характерный угол раскрытия на E ≈ E_c."""
        return 1e3 / self.gamma


# --------------------------------------------------------------------------- G1
def _int_k53(y: float) -> float:
    """∫_y^∞ K_{5/3}(t) dt. Подстановка t = y e^u устраняет особенность при малых y."""
    if y > 700:
        return 0.0
    u_max = np.log(700.0 / y)  # K_{5/3}(700) ~ 1e-305 — дальше вклад пренебрежим
    f = lambda u: special.kv(5.0 / 3.0, y * np.exp(u)) * y * np.exp(u)
    val, _ = integrate.quad(f, 0.0, u_max, limit=500, epsabs=0.0, epsrel=1e-10)
    return val


def G1(y):
    """G1(y) = y ∫_y^∞ K_{5/3}. Векторизовано."""
    y = np.atleast_1d(np.asarray(y, dtype=float))
    out = np.array([yy * _int_k53(yy) if yy > 0 else 0.0 for yy in y])
    return out


INTEGRAL_G1 = 8.0 * np.pi / (9.0 * np.sqrt(3.0))   # ∫_0^∞ G1(y) dy — для проверки нормировки мощности


def flux_per_mrad(src: Source, E_keV):
    """dN/(dt dθ dE): фотоны / (с · мрад_гориз · кэВ) при токе src.current_mA."""
    E = np.atleast_1d(np.asarray(E_keV, dtype=float))
    y = E / src.critical_energy_keV
    pref = np.sqrt(3.0) / (2 * np.pi) * ALPHA * src.gamma * (src.current_mA * 1e-3 / E_CHARGE) * 1e-3  # на мрад
    return pref * G1(y) / E


def power_per_mrad_W(src: Source) -> float:
    """Аналитическая мощность на единицу горизонтального угла: (4/9) α γ (I/e) E_c, Вт/мрад."""
    Ec_J = src.critical_energy_keV * 1e3 * E_CHARGE
    return 4.0 / 9.0 * ALPHA * src.gamma * (src.current_mA * 1e-3 / E_CHARGE) * Ec_J * 1e-3


# ------------------------------------------------------------- вертикальный угол
def angular_flux(src: Source, E_keV, psi_mrad, components: bool = False):
    """d²N/(dt dθ dψ dE): фотоны / (с · мрад_гориз · мрад_верт · кэВ).

    Возвращает массив формы (len(E), len(psi)); при components=True — (σ, π).
    """
    E = np.atleast_1d(np.asarray(E_keV, dtype=float))[:, None]
    psi = np.atleast_1d(np.asarray(psi_mrad, dtype=float))[None, :] * 1e-3
    y = E / src.critical_energy_keV
    X = src.gamma * psi
    one = 1.0 + X ** 2
    xi = 0.5 * y * one ** 1.5
    k23 = special.kv(2.0 / 3.0, xi)
    k13 = special.kv(1.0 / 3.0, xi)
    pref = 3 * ALPHA / (4 * np.pi ** 2) * src.gamma ** 2 * (src.current_mA * 1e-3 / E_CHARGE) * 1e-6  # на мрад²
    common = pref * y ** 2 * one ** 2 / E  # переход от dE/E к dE
    sig = common * k23 ** 2
    pi = common * (X ** 2 / one) * k13 ** 2
    sig = np.where(np.isfinite(sig), sig, 0.0)
    pi = np.where(np.isfinite(pi), pi, 0.0)
    return (sig, pi) if components else sig + pi


def psi_rms_mrad(src: Source, E_keV: float, psi_max_mrad: float = 5.0, n: int = 4001) -> float:
    """Среднеквадратичный вертикальный угол на энергии E (для отчётов)."""
    psi = np.linspace(-psi_max_mrad, psi_max_mrad, n)
    f = angular_flux(src, [E_keV], psi)[0]
    return float(np.sqrt(trapz(f * psi ** 2, psi) / trapz(f, psi)))


def bin_integrate_2d(src: Source, e_edges, psi_edges, sub_e: int = 4, sub_psi: int = 4):
    """Интеграл d²N/(dθ dψ dE) по ячейкам сетки (E × ψ) методом Гаусса–Лежандра.

    Возвращает (σ, π) — фотоны / (с · мрад_гориз) в каждой ячейке. Нормировка
    определяется реальными ширинами ячеек (требование ТЗ, п. 2.3).
    """
    e_edges = np.asarray(e_edges, float)
    psi_edges = np.asarray(psi_edges, float)
    xe, we = np.polynomial.legendre.leggauss(sub_e)
    xp, wp = np.polynomial.legendre.leggauss(sub_psi)
    eh = 0.5 * np.diff(e_edges)
    ec = 0.5 * (e_edges[1:] + e_edges[:-1])
    ph = 0.5 * np.diff(psi_edges)
    pc = 0.5 * (psi_edges[1:] + psi_edges[:-1])
    sig = np.zeros((len(ec), len(pc)))
    pi = np.zeros_like(sig)
    for i in range(sub_e):
        E = ec + eh * xe[i]
        for j in range(sub_psi):
            P = pc + ph * xp[j]
            s, p = angular_flux(src, E, P, components=True)
            w = (we[i] * eh)[:, None] * (wp[j] * ph)[None, :]
            sig += s * w
            pi += p * w
    return sig, pi

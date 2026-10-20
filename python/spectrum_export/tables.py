"""Таблицы источника для Geant4 и нормировка потока.

Совместная таблица (E, ψ, поляризация) интегрируется по ячейкам сетки
(не «значение функции × ширина») и, при необходимости, умножается на
аналитическое пропускание фильтров exp(-μd) (нерассеянная компонента).
Веса — фотоны / (с · мрад_гориз) при опорном токе.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from material_attenuation.materials import Material, transmission
from synchrotron_spectrum.sr import E_CHARGE, Source, bin_integrate_2d


@dataclass
class SpectrumGrid:
    e_min_keV: float = 1.0
    e_max_keV: float = 80.0
    e_step_keV: float = 0.1
    psi_max_mrad: float = 1.5
    psi_step_mrad: float = 0.02

    def e_edges(self) -> np.ndarray:
        n = int(round((self.e_max_keV - self.e_min_keV) / self.e_step_keV))
        return np.linspace(self.e_min_keV, self.e_min_keV + n * self.e_step_keV, n + 1)

    def psi_edges(self, limit_mrad: float | None = None) -> np.ndarray:
        pm = self.psi_max_mrad if limit_mrad is None else min(self.psi_max_mrad, limit_mrad)
        n = int(np.ceil(pm / self.psi_step_mrad))
        e = np.linspace(-n * self.psi_step_mrad, n * self.psi_step_mrad, 2 * n + 1)
        if limit_mrad is not None and limit_mrad < n * self.psi_step_mrad:
            e = np.clip(e, -limit_mrad, limit_mrad)
            e = np.unique(e)
        return e


@dataclass
class JointTable:
    e_edges: np.ndarray
    psi_edges: np.ndarray
    sigma: np.ndarray           # [nE, nψ] фотоны/(с·мрад_гориз) в ячейке
    pi: np.ndarray
    filters: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    @property
    def total(self) -> np.ndarray:
        return self.sigma + self.pi

    def energy_spectrum(self) -> np.ndarray:
        """Фотоны/(с·мрад_гориз) в каждом энергетическом бине (интеграл по ψ)."""
        return self.total.sum(axis=1)

    def summary(self) -> dict:
        ec = 0.5 * (self.e_edges[1:] + self.e_edges[:-1])
        n = self.energy_spectrum()
        N = float(n.sum())
        P = float((n * ec).sum() * 1e3 * E_CHARGE)  # Вт/мрад_гориз
        return {"photons_per_s_per_mrad": N, "power_W_per_mrad": P,
                "mean_energy_keV": float((n * ec).sum() / N) if N > 0 else 0.0,
                "sigma_fraction": float(self.sigma.sum() / max(N, 1e-300))}

    def write_csv(self, path: Path, header_lines: list[str] | None = None, rel_cut: float = 1e-12) -> int:
        """CSV для liga_sim: e_lo,e_hi,psi_lo,psi_hi,w_sigma,w_pi. Отбрасывает ничтожные ячейки."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tot = self.total
        thr = rel_cut * tot.max()
        n = 0
        with open(path, "w", encoding="utf-8") as f:
            for h in header_lines or []:
                f.write(f"# {h}\n")
            f.write("# weights: photons / (s * mrad_horizontal) per cell at the reference current\n")
            f.write("e_lo_keV,e_hi_keV,psi_lo_mrad,psi_hi_mrad,w_sigma,w_pi\n")
            for i in range(len(self.e_edges) - 1):
                for j in range(len(self.psi_edges) - 1):
                    if tot[i, j] <= thr:
                        continue
                    f.write(f"{self.e_edges[i]:.6g},{self.e_edges[i+1]:.6g},{self.psi_edges[j]:.6g},"
                            f"{self.psi_edges[j+1]:.6g},{self.sigma[i, j]:.8e},{self.pi[i, j]:.8e}\n")
                    n += 1
        return n


def build_joint_table(src: Source, grid: SpectrumGrid, filters: list[tuple[Material, float]] | None = None,
                      psi_limit_mrad: float | None = None) -> JointTable:
    """Совместная таблица после аналитических фильтров (материал, толщина в мкм)."""
    e_edges = grid.e_edges()
    psi_edges = grid.psi_edges(psi_limit_mrad)
    sig, pi = bin_integrate_2d(src, e_edges, psi_edges)
    filters = filters or []
    if filters:
        # Пропускание усредняем по бину энергии (5 узлов Гаусса), чтобы края поглощения
        # внутри бина не давали систематической ошибки.
        xg, wg = np.polynomial.legendre.leggauss(5)
        ec = 0.5 * (e_edges[1:] + e_edges[:-1])
        eh = 0.5 * np.diff(e_edges)
        T = np.zeros_like(ec)
        for k in range(5):
            Ek = ec + eh * xg[k]
            t = np.ones_like(Ek)
            for mat, d_um in filters:
                t *= transmission(mat, d_um, Ek)
            T += 0.5 * wg[k] * t
        sig = sig * T[:, None]
        pi = pi * T[:, None]
    return JointTable(e_edges, psi_edges, sig, pi,
                      filters=[(m.name, d) for m, d in filters])


def scan_averaged_fluence_rate(table: JointTable, distance_m: float, scan_half_mm: float) -> float:
    """Средний по сканированию поток фотонов в точке образца, фотоны/(с·мм²).

    Горизонталь: 1 мрад ↔ L·1e-3 мм. Вертикаль: при равномерном сканировании с
    амплитудой ±A весь вертикальный интеграл распределяется по пути 2A
    (условие: вертикальный размер пучка < A, выполняется: ±6 мм < 15 мм).
    """
    N = float(table.total.sum())
    return N / (distance_m * 1e3 * 1e-3) / (2.0 * scan_half_mm)


def static_fluence_rate(table: JointTable, distance_m: float, psi_mrad: float = 0.0) -> float:
    """Поток в неподвижной точке на угле ψ: фотоны/(с·мм²)."""
    j = int(np.searchsorted(table.psi_edges, psi_mrad, side="right") - 1)
    dpsi = table.psi_edges[j + 1] - table.psi_edges[j]
    per_mrad2 = float(table.total[:, j].sum()) / dpsi
    return per_mrad2 / (distance_m * 1e3 * 1e-3) ** 2


def write_gps_macro(table: JointTable, path: Path, z_mm: float, half_x_mm: float, half_y_mm: float) -> None:
    """Режим A: макрос G4GeneralParticleSource с произвольным (Arb) спектром.

    Точки гистограммы — центры бинов и плотность (фотоны/кэВ); направление +Z,
    равномерная квадратная плоскость. Угловые корреляции в режиме A не учитываются.
    """
    ec = 0.5 * (table.e_edges[1:] + table.e_edges[:-1])
    dens = table.energy_spectrum() / np.diff(table.e_edges)
    keep = dens > 1e-12 * dens.max()
    lines = ["/gps/particle gamma", "/gps/pos/type Plane", "/gps/pos/shape Square",
             f"/gps/pos/centre 0 0 {z_mm:.9g} mm", f"/gps/pos/halfx {half_x_mm:.9g} mm",
             f"/gps/pos/halfy {half_y_mm:.9g} mm", "/gps/direction 0 0 1", "/gps/ene/type Arb",
             "/gps/hist/type arb"]
    for e, d in zip(ec[keep], dens[keep]):
        lines.append(f"/gps/hist/point {e * 1e-3:.9g} {d:.9g}")
    lines.append("/gps/hist/inter Lin")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

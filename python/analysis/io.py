"""Загрузка результатов liga_sim (HDF5) и перевод в физическую дозу.

Доза в ячейке:  D = (Σ_w Edep / N) · Φ_inc · A_win / V      [Дж/см³],
в Гр — делением на плотность ПММА. Погрешность — по независимым историям:
    s²(mean) = (Σx²/N − (Σx/N)²) / (N − 1).
Интегральные распределения (по глубине и т.п.) строятся как Σ E / Σ m,
а не как сумма доз (ТЗ п. 6.3).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import h5py
import numpy as np

MEV_TO_J = 1.602176634e-13


@dataclass
class Grid:
    name: str
    x: np.ndarray  # границы, мкм
    y: np.ndarray
    z: np.ndarray
    edep: np.ndarray           # [nx,ny,nz] МэВ·вес (сумма по историям)
    edep_sq: np.ndarray
    cat: np.ndarray | None     # [ncat,nx,ny,nz]
    feat: np.ndarray | None    # [nfeat,...]
    mem_sq: np.ndarray | None
    col_sq: np.ndarray | None  # [nx,ny] сумма квадратов по историям для колонок (сумма по z)
    cat_names: list[str]
    feat_names: list[str]

    @property
    def xc(self):
        return 0.5 * (self.x[1:] + self.x[:-1])

    @property
    def yc(self):
        return 0.5 * (self.y[1:] + self.y[:-1])

    @property
    def zc(self):
        return 0.5 * (self.z[1:] + self.z[:-1])

    def volumes_cm3(self) -> np.ndarray:
        dx, dy, dz = np.diff(self.x), np.diff(self.y), np.diff(self.z)
        return (dx[:, None, None] * dy[None, :, None] * dz[None, None, :]) * 1e-12


@dataclass
class Run:
    path: Path
    info: dict
    meta: dict
    grids: dict[str, Grid]
    spectra: dict
    balance: dict
    n: int
    density_g_cm3: float

    # ----- нормировка
    @property
    def scale_J(self) -> float:
        """Множитель: (Σ Edep [МэВ]) → энергия [Дж] на экспозицию эксперимента."""
        nrm = self.info["normalization"]
        return nrm["incident_fluence_ph_mm2"] * nrm["window_area_mm2"] / self.n * MEV_TO_J

    @property
    def scale_J_per_photon(self) -> float:
        """Энергия [Дж] на один падающий фотон на мм² (для «дозы на единицу флюенса»)."""
        nrm = self.info["normalization"]
        return nrm["window_area_mm2"] / self.n * MEV_TO_J

    def dose(self, grid: str = "map3d", what: str = "total", index: int | None = None, per: str = "exposure"):
        """Доза Дж/см³ в ячейках. what: total | category | feature."""
        g = self.grids[grid]
        if what == "total":
            e = g.edep
        elif what == "category":
            e = g.cat[index]
        elif what == "feature":
            e = g.feat[index]
        else:
            raise ValueError(what)
        s = self.scale_J if per == "exposure" else self.scale_J_per_photon
        return e * s / g.volumes_cm3()

    def dose_sigma(self, grid: str = "map3d", membrane: bool = False, per: str = "exposure"):
        """Стандартная погрешность дозы (по историям), Дж/см³."""
        g = self.grids[grid]
        s1 = g.edep if not membrane else g.feat[0]
        s2 = g.edep_sq if not membrane else g.mem_sq
        n = self.n
        var = np.clip(s2 / n - (s1 / n) ** 2, 0, None) / max(n - 1, 1)
        s = self.scale_J if per == "exposure" else self.scale_J_per_photon
        return np.sqrt(var) * n * s / g.volumes_cm3()


def load_run(run_dir: Path) -> Run:
    run_dir = Path(run_dir)
    info = json.loads((run_dir / "run_info.json").read_text(encoding="utf-8"))
    path = run_dir / "stage2" / "stage2.h5"
    grids = {}
    with h5py.File(path, "r") as f:
        meta = {k: (v.decode() if isinstance(v, bytes) else v) for k, v in f["meta"].attrs.items()}
        n = int(meta["n_events"])
        for name, g in f["grids"].items():
            has = "edep_category_MeV" in g
            grids[name] = Grid(
                name, g["x_edges_um"][:], g["y_edges_um"][:], g["z_edges_um"][:], g["edep_MeV"][:], g["edep_sq_MeV2"][:],
                g["edep_category_MeV"][:] if has else None, g["edep_feature_MeV"][:] if has else None,
                g["edep_membrane_sq_MeV2"][:] if has else None,
                g["column_sq_MeV2"][:] if "column_sq_MeV2" in g else None,
                g.attrs["category_names"].decode().split(",") if has else [],
                g.attrs["feature_names"].decode().split(",") if has else [])
        spectra = {k: v[:] for k, v in f["spectra"].items()}
        spectra.update({k: (v.decode() if isinstance(v, bytes) else v) for k, v in f["spectra"].attrs.items()})
        bal = {k: (v.decode() if isinstance(v, bytes) else v) for k, v in f["balance"].attrs.items()}
        bal["edep_by_role_MeV"] = f["balance/edep_by_role_MeV"][:]
    cfg = json.loads(meta["config_json"])
    rho = float(cfg["materials"]["PMMA"]["density_g_cm3"])
    return Run(run_dir, info, meta, grids, spectra, bal, n, rho)

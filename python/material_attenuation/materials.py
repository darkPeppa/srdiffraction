"""Реестр материалов и коэффициенты ослабления фотонов.

Источник составов и плотностей — config/materials.yaml (с провенансом).
Коэффициенты μ/ρ — таблицы NIST (Hubbell & Seltzer, data/reference_data/
nist_xraymasscoef) с лог-лог интерполяцией между краями поглощения и
правилом аддитивности по массовым долям (как в XCOM). Альтернатива —
таблица Geant4 (G4EmCalculator), получаемая командой `liga materials`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

from liga_common.paths import REPO

NIST_DIR = REPO / "data" / "reference_data" / "nist_xraymasscoef"

ATOMIC_MASS = {  # г/моль (IUPAC 2013, стандартные атомные массы)
    "H": 1.008, "He": 4.002602, "Be": 9.0121831, "C": 12.011, "N": 14.007, "O": 15.999,
    "Al": 26.9815385, "Si": 28.085, "Ar": 39.948, "Ti": 47.867, "Cu": 63.546, "Au": 196.966569,
}


@dataclass
class Material:
    name: str
    density_g_cm3: float
    mass_fractions: dict[str, float] = field(default_factory=dict)
    nist: str = ""                    # имя материала NIST в Geant4 (если используется)
    state: str = "solid"
    pressure_Pa: float = 101325.0
    temperature_K: float = 293.15
    provenance: dict = field(default_factory=dict)

    def to_geant4(self) -> dict:
        d = {"density_g_cm3": self.density_g_cm3, "state": self.state,
             "pressure_Pa": self.pressure_Pa, "temperature_K": self.temperature_K}
        if self.nist:
            d["nist"] = self.nist
        else:
            d["mass_fractions"] = self.mass_fractions
        return d


def fractions_from_formula(atoms: dict[str, float]) -> dict[str, float]:
    m = {el: n * ATOMIC_MASS[el] for el, n in atoms.items()}
    tot = sum(m.values())
    return {el: v / tot for el, v in m.items()}


def gas_density_g_cm3(molar_mass_g_mol: float, pressure_Pa: float, temperature_K: float) -> float:
    """Идеальный газ: ρ = P M / (R T)."""
    return pressure_Pa * molar_mass_g_mol / (8.314462618 * temperature_K) * 1e-6


def build_materials(spec: dict) -> dict[str, Material]:
    """Из разобранного materials.yaml (уже без обёрток провенанса)."""
    out = {}
    for name, m in spec.items():
        if "formula" in m:
            fr = fractions_from_formula(m["formula"])
        else:
            fr = dict(m.get("mass_fractions", {}))
        s = sum(fr.values())
        if fr and abs(s - 1) > 1e-6:
            fr = {k: v / s for k, v in fr.items()}
        state = m.get("state", "solid")
        rho = m.get("density_g_cm3")
        if state == "gas" and rho is None:
            # молярная масса МОЛЕКУЛ: для многоатомных газов (N₂, O₂) задаётся явно в YAML
            molar = m.get("molar_mass_g_mol") or 1.0 / sum(f / ATOMIC_MASS[el] for el, f in fr.items())
            rho = gas_density_g_cm3(molar, m["pressure_Pa"], m.get("temperature_K", 293.15))
        out[name] = Material(name=name, density_g_cm3=float(rho), mass_fractions=fr, nist=m.get("nist", ""),
                             state=state, pressure_Pa=m.get("pressure_Pa", 101325.0),
                             temperature_K=m.get("temperature_K", 293.15))
    return out


# --------------------------------------------------------------------- NIST
@lru_cache(maxsize=None)
def _nist_table(element: str):
    path = NIST_DIR / f"{element}.csv"
    if not path.exists():
        raise FileNotFoundError(f"NIST table for {element} not found: {path}")
    rows = [l.split(",") for l in path.read_text().splitlines() if l and not l.startswith("#")][1:]
    E = np.array([float(r[0]) for r in rows])
    mu = np.array([float(r[1]) for r in rows])
    muen = np.array([float(r[2]) for r in rows])
    return E, mu, muen


def _loglog_interp(E_tab, v_tab, E):
    """Лог-лог интерполяция с учётом краёв поглощения.

    В таблицах NIST край записан двумя строками с одинаковой энергией
    (значение ниже и выше края). Таблица делится на непрерывные сегменты;
    точка, совпадающая с краем, относится к сегменту ВЫШЕ края.
    """
    E = np.atleast_1d(np.asarray(E, float))
    cuts = np.where(np.diff(E_tab) == 0)[0]
    starts = np.r_[0, cuts + 1]
    ends = np.r_[cuts + 1, len(E_tab)]
    lows = E_tab[starts]
    out = np.empty_like(E)
    for k, e in enumerate(E):
        seg = int(np.searchsorted(lows, e, side="right")) - 1
        seg = min(max(seg, 0), len(starts) - 1)
        s, t = starts[seg], ends[seg]
        out[k] = np.exp(np.interp(np.log(e), np.log(E_tab[s:t]), np.log(v_tab[s:t])))
    return out


def mu_rho_nist(material: Material, E_keV, kind: str = "total"):
    """μ/ρ (см²/г) по NIST + правило смеси. kind: total | en."""
    E = np.atleast_1d(np.asarray(E_keV, float))
    if not material.mass_fractions:
        raise ValueError(f"material {material.name}: mass fractions required for NIST mixture rule")
    res = np.zeros_like(E)
    for el, w in material.mass_fractions.items():
        Et, mu, muen = _nist_table(el)
        res += w * _loglog_interp(Et, mu if kind == "total" else muen, E)
    return res


def transmission(material: Material, thickness_um: float, E_keV, source: str = "nist", xs=None):
    """Пропускание нерассеянной компоненты exp(-μ d) для слоя толщиной d."""
    if source == "nist":
        mu_lin = mu_rho_nist(material, E_keV) * material.density_g_cm3  # 1/см
    elif source == "geant4":
        if xs is None:
            raise ValueError("geant4 source requires an xs table")
        mu_lin = xs(material.name, E_keV)
    else:
        raise ValueError(source)
    return np.exp(-mu_lin * thickness_um * 1e-4)


class Geant4XS:
    """Таблица коэффициентов из `liga_sim` (run.mode = xs_table)."""

    def __init__(self, csv_path: Path):
        import pandas as pd
        self.df = pd.read_csv(csv_path, comment="#")

    def components(self, layer_name: str):
        d = self.df[self.df.material == layer_name].sort_values("energy_keV")
        if d.empty:
            raise KeyError(layer_name)
        return d

    def __call__(self, layer_name: str, E_keV):
        d = self.components(layer_name)
        return np.exp(np.interp(np.log(np.atleast_1d(E_keV)), np.log(d.energy_keV), np.log(d.mu_total_cm)))

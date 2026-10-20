"""Сборка модели эксперимента из YAML: материалы, источник, слои этапов 1/2, сетки.

Координаты (мм, вдоль пучка +Z): z = 0 — передняя грань рентгеношаблона
(первый слой шаблона по пучку). Всё, что ближе к источнику, имеет z < 0.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from liga_common.io import load_yaml
from liga_common.params import Provenance, deep_merge, unwrap
from liga_common.paths import CONFIG
from material_attenuation.materials import Material, build_materials
from synchrotron_spectrum.sr import Source

EXPERIMENTS = ["be_200", "carbon_475", "sapphire_contact", "sapphire_280mm", "titanium_model"]
PMMA_REQUIRED_UM = 15.0
GAS_PAD_UM = 1.0  # плоскость генерации/фазового пространства — за 1 мкм до первого слоя этапа 2


@dataclass
class Layer:
    name: str
    role: str
    material: str
    thickness_um: float
    z_front_mm: float
    half_x_mm: float = 0.0
    half_y_mm: float = 0.0
    hole_um: float | None = None
    prod_cut_um: float | None = None

    @property
    def z_back_mm(self) -> float:
        return self.z_front_mm + self.thickness_um * 1e-3

    def to_json(self) -> dict:
        d = {"name": self.name, "role": self.role, "material": self.material, "thickness_um": self.thickness_um,
             "z_front_mm": self.z_front_mm, "half_x_mm": self.half_x_mm, "half_y_mm": self.half_y_mm}
        if self.hole_um:
            d["hole"] = {"size_x_um": self.hole_um, "size_y_um": self.hole_um, "center_x_um": 0.0, "center_y_um": 0.0}
        if self.prod_cut_um:
            d["prod_cut_um"] = self.prod_cut_um
        return d


@dataclass
class Experiment:
    id: str
    raw: dict
    prov: Provenance
    source: dict
    spectrum: dict
    materials: dict[str, Material]
    sim: dict
    overrides: dict = field(default_factory=dict)

    # ---------------------------------------------------------------- свойства
    @property
    def exp(self) -> dict:
        return self.raw["experiment"]

    @property
    def geo(self) -> dict:
        return self.raw["geometry"]

    @property
    def holes(self) -> list[float]:
        return list(self.exp["holes_um"])

    @property
    def src(self) -> Source:
        return Source(self.source["electron_energy_GeV"], self.source["field_T"], self.source["current_reference_mA"])

    @property
    def remote_membrane(self) -> bool:
        return self.geo["membrane"] is not None and self.geo["membrane"].get("position") == "remote"

    # ------------------------------------------------------------------ слои
    def mask_stack(self, hole_um: float, half_xy_mm: float, cuts: dict) -> list[Layer]:
        g = self.geo
        m = g["mask"]
        au = Layer(m["absorber"]["name"], "absorber", m["absorber"]["material"], float(m["absorber"]["thickness_um"]),
                   0.0, half_xy_mm, half_xy_mm, hole_um=hole_um)
        ti = Layer(m["support"]["name"], "mask_support", m["support"]["material"], float(m["support"]["thickness_um"]),
                   0.0, half_xy_mm, half_xy_mm)
        order = [au, ti] if m.get("orientation", "au_upstream") == "au_upstream" else [ti, au]
        z = 0.0
        out = []
        for l in order:
            l.z_front_mm = z
            z = l.z_back_mm
            out.append(l)
        z += float(g.get("mask_to_kapton_gap_um", 0)) * 1e-3
        kap = Layer("Kapton", "kapton", "Kapton", float(g["kapton_um"]), z, half_xy_mm, half_xy_mm,
                    prod_cut_um=cuts.get("Kapton"))
        out.append(kap)
        z = kap.z_back_mm + float(g.get("kapton_to_pmma_gap_um", 0)) * 1e-3
        pm_t = float(g["pmma_um"])
        if abs(pm_t - PMMA_REQUIRED_UM) > 1e-9 and not self.overrides.get("allow_nonstandard_pmma"):
            raise ValueError(f"PMMA thickness {pm_t} µm differs from the fixed 15 µm (ТЗ п. 1.2). "
                             "Use --allow-nonstandard-pmma explicitly for sensitivity studies.")
        pm = Layer("PMMA", "pmma", "PMMA", pm_t, z, half_xy_mm, half_xy_mm, prod_cut_um=cuts.get("PMMA"))
        out.append(pm)
        sub = g.get("substrate")
        if sub:
            out.append(Layer("Substrate", "substrate", sub["material"], float(sub["thickness_um"]), pm.z_back_mm,
                             half_xy_mm, half_xy_mm))
        return out

    def membrane_layer(self, half_xy_mm: float) -> Layer | None:
        mem = self.geo.get("membrane")
        if not mem or self.overrides.get("no_membrane"):
            return None
        t = float(mem["thickness_um"])
        if mem["position"] == "contact":
            zb = -float(mem.get("gap_to_mask_um", 0)) * 1e-3
        else:
            zb = -float(mem["distance_to_mask_mm"])
        return Layer(mem["name"], "test_membrane", mem["material"], t, zb - t * 1e-3, half_xy_mm, half_xy_mm)

    def al_layer(self, membrane_front_mm: float, half_xy_mm: float) -> Layer:
        t = float(self.geo["al_filter_um"])
        zb = membrane_front_mm - float(self.geo["al_to_membrane_mm"])
        return Layer("AlFilter", "al_filter", "Al", t, zb - t * 1e-3, half_xy_mm, half_xy_mm)

    def stage_layers(self, hole_um: float, window_half_mm: float) -> tuple[list[Layer], list[Layer], float]:
        """(слои этапа 1, слои этапа 2, z плоскости передачи фазового пространства)."""
        cuts = self.sim["physics"].get("region_cuts_um", {})
        local_half = window_half_mm + 2.0  # слои этапа 2 шире окна генерации
        stack = self.mask_stack(hole_um, local_half, cuts)
        remote_half = 150.0                 # «бесконечные» удалённые пластины (этап 1)
        mem = self.membrane_layer(local_half)
        stage1: list[Layer] = []
        if mem is not None and self.remote_membrane:
            mem.half_x_mm = mem.half_y_mm = remote_half
            stage1.append(mem)
            al = self.al_layer(mem.z_front_mm, remote_half)
            stage2 = stack
        elif mem is not None:
            al = self.al_layer(mem.z_front_mm, remote_half)
            stage2 = [mem] + stack
        else:
            # Контроль без мембраны: Al остаётся на том же месте, что и в полной конфигурации.
            m0 = self.geo["membrane"]
            if m0 and m0["position"] == "remote":
                zf = -float(m0["distance_to_mask_mm"]) - float(m0["thickness_um"]) * 1e-3
            elif m0:
                zf = -float(m0.get("gap_to_mask_um", 0)) * 1e-3 - float(m0["thickness_um"]) * 1e-3
            else:
                zf = 0.0
            al = self.al_layer(zf, remote_half)
            stage2 = stack
        stage1.insert(0, al)
        plane = stage2[0].z_front_mm - GAS_PAD_UM * 1e-3
        return stage1, stage2, plane

    # --------------------------------------------------------------- материалы
    def materials_json(self, names: set[str]) -> dict:
        return {n: self.materials[n].to_geant4() for n in names}

    def medium(self) -> str:
        return self.overrides.get("medium") or self.geo.get("medium") or "Vacuum"


def load_experiment(exp_id: str, overrides: dict | None = None) -> Experiment:
    path = CONFIG / f"{exp_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"unknown experiment '{exp_id}' (no {path})")
    prov = Provenance()
    raw_exp = load_yaml(path)
    raw_src = load_yaml(CONFIG / "source.yaml")
    raw_mat = load_yaml(CONFIG / "materials.yaml")
    raw_sim = load_yaml(CONFIG / "simulation.yaml")
    overrides = overrides or {}
    # Пользовательские переопределения геометрии (например, для анализа чувствительности)
    if overrides.get("geometry"):
        raw_exp = copy.deepcopy(raw_exp)
        raw_exp["geometry"] = deep_merge(raw_exp["geometry"], overrides["geometry"])
    exp = unwrap(raw_exp, prov, exp_id)
    src = unwrap(raw_src, prov, "source")
    mats = unwrap(raw_mat, prov, "materials")["materials"]
    if overrides.get("materials"):
        for k, v in overrides["materials"].items():
            mats[k] = deep_merge(mats[k], v)
    sim = unwrap(raw_sim)
    if overrides.get("physics"):
        sim["physics"] = deep_merge(sim["physics"], overrides["physics"])
    if overrides.get("source"):
        src["source"] = deep_merge(src["source"], overrides["source"])
    return Experiment(exp_id, exp, prov, src["source"], src["spectrum"], build_materials(mats), sim, overrides)


# ------------------------------------------------------------------------- сетки
def _edges_with_fine_zones(lo: float, hi: float, fine_centers: list[float], fine_half: float, fine: float,
                           coarse: float) -> np.ndarray:
    """Границы ячеек на [lo, hi]: шаг `fine` в зонах |x - c| < fine_half, иначе `coarse`."""
    zones = sorted((max(lo, c - fine_half), min(hi, c + fine_half)) for c in fine_centers)
    merged = []
    for a, b in zones:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    edges = [lo]
    x = lo
    for a, b in merged + [(hi, hi)]:
        # грубый участок [x, a]
        if a > x:
            n = max(1, int(np.ceil((a - x) / coarse - 1e-9)))
            edges += list(np.linspace(x, a, n + 1)[1:])
            x = a
        if b > x:
            n = max(1, int(np.ceil((b - x) / fine - 1e-9)))
            edges += list(np.linspace(x, b, n + 1)[1:])
            x = b
    e = np.unique(np.round(np.array(edges), 9))
    return e


def scoring_grids(hole_um: float, sc: dict, pmma_um: float) -> list[dict]:
    h2 = 0.5 * hole_um
    ext = h2 + sc["outside_margin_um"]
    xy = _edges_with_fine_zones(-ext, ext, [-h2, h2], sc["fine_halfwidth_um"], sc["fine_bin_um"], sc["coarse_bin_um"])
    nz = int(round(pmma_um / sc["z_bin_um"]))
    z = np.linspace(0, pmma_um, nz + 1)
    strip_x = _edges_with_fine_zones(-ext, ext, [-h2, h2], sc["strip_halfwidth_um"], sc["strip_bin_um"],
                                     sc["coarse_bin_um"])
    # Полоса поперёк левого/правого краёв вдоль всей длины края, исключая углы
    # (|y| < h/2 − corner_margin), но не уже h/4 для маленьких отверстий.
    hy = max(hole_um / 2.0 - sc["strip_corner_margin_um"], hole_um / 4.0)
    nzs = int(round(pmma_um / sc["strip_z_bin_um"]))
    return [
        {"name": "map3d", "x_edges_um": xy.tolist(), "y_edges_um": xy.tolist(), "z_edges_um": z.tolist(),
         "categories": True},
        {"name": "edge_strip", "x_edges_um": strip_x.tolist(), "y_edges_um": [-hy, hy],
         "z_edges_um": np.linspace(0, pmma_um, nzs + 1).tolist(), "categories": True},
    ]

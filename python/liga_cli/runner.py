"""Запуск liga_sim: подготовка таблиц источника, JSON-конфигураций этапов 1/2, нормировка."""
from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from liga_common.io import dump_json, environment_info
from liga_common.paths import LIGA_SIM, ensure
from spectrum_export.tables import (JointTable, SpectrumGrid, build_joint_table, scan_averaged_fluence_rate,
                                    write_gps_macro)

from .model import Experiment, Layer, scoring_grids

MEV_TO_J = 1.602176634e-13


@dataclass
class RunOptions:
    profile: str = "quick"
    upstream: str = "stage1"          # stage1 (явный транспорт Al/удалённой мембраны) | analytic
    stage1_events: int | None = None
    stage2_events: int | None = None
    window_extra_mm: float | None = None
    threads: int = 0
    seed: int | None = None
    psi_limit_mrad: float | None = None  # ограничение апертуры канала (анализ чувствительности)
    tag: str = ""


def run_liga_sim(cfg: dict, json_path: Path, log_path: Path) -> float:
    """Запустить liga_sim, вывод — в лог и на экран. Возвращает время выполнения, с."""
    dump_json(cfg, json_path)
    t0 = time.time()
    cmd = [LIGA_SIM, str(json_path)]
    print(f"$ {' '.join(shlex.quote(c) for c in cmd)}", flush=True)
    benign = 0
    with open(log_path, "w", encoding="utf-8") as log:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in p.stdout:
            log.write(line)
            if "BIAS.GEN.0" in line or "WWWW" in line:
                benign += 1  # известные безвредные предупреждения смещения (docs/validation.md) — только в лог
                continue
            if line.startswith("[liga]") or "Exception" in line or "ERROR" in line or "error" in line.lower():
                sys.stdout.write("  " + line)
        rc = p.wait()
    if benign:
        print(f"  (безвредные предупреждения смещения BIAS.GEN — {benign // 3} шт., см. {Path(log_path).name})")
    if rc != 0:
        tail = Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
        raise RuntimeError(f"liga_sim failed (rc={rc}); log {log_path}:\n" + "\n".join(tail))
    return time.time() - t0


def source_table(exp: Experiment, analytic_layers: list[Layer], psi_limit_mrad: float | None) -> JointTable:
    """Таблица после Be-окон (аналитически) и, при необходимости, аналитических слоёв (режим analytic)."""
    s = exp.source
    grid = SpectrumGrid(exp.spectrum["e_min_keV"], exp.spectrum["e_max_keV"], exp.spectrum["e_step_keV"],
                        exp.spectrum["psi_max_mrad"], exp.spectrum["psi_step_mrad"])
    filters = [(exp.materials["Be"], float(s["be_windows"]["total_um"]))]
    for l in analytic_layers:
        filters.append((exp.materials[l.material], l.thickness_um))
    scan_limit = s["scan_half_amplitude_mm"] / (s["distance_m"] * 1e3) * 1e3 if s.get("scan_mode") != "none" else None
    limits = [v for v in (scan_limit, psi_limit_mrad, s.get("channel_aperture_mrad")) if v]
    return build_joint_table(exp.src, grid, filters, min(limits) if limits else None)


def _base_cfg(exp: Experiment, name: str, out: Path, n: int, seed: int, threads: int) -> dict:
    ph = exp.sim["physics"]
    return {
        "run": {"name": name, "mode": "transport", "n_events": int(n), "seed": int(seed), "threads": int(threads),
                "output": str(out), "progress_every": max(1, int(n) // 10)},
        "physics": {k: ph[k] for k in ("em", "fluo", "auger", "pixe", "deexcitation_ignore_cut", "default_cut_um",
                                       "lowest_electron_energy_eV", "cuts_table_low_edge_eV",
                                       "kill_unreachable_electrons", "force_collision_roles") if k in ph},
    }


def _source_common(exp: Experiment) -> dict:
    s = exp.source
    return {
        "distance_m": s["distance_m"],
        "scan_mode": s.get("scan_mode", "averaged"),
        "scan_half_amplitude_mm": s["scan_half_amplitude_mm"],
        "source_sigma_x_mm": s["source_size_h_mm"] / 2.3548,
        "source_sigma_y_mm": s["source_size_v_mm"] / 2.3548,
        "electron_divergence_sigma_mrad": s["electron_divergence_mrad"],
        "beam_half_x_mm": s["beam_size_h_mm"] / 2.0,
        "polarization": True,
    }


def _world(layers: list[Layer], z_extra: list[float], half_xy: float) -> tuple[float, float]:
    zs = [l.z_front_mm for l in layers] + [l.z_back_mm for l in layers] + z_extra
    return half_xy, max(abs(min(zs)), abs(max(zs))) + 1.0


def simulate(exp: Experiment, hole_um: float, opts: RunOptions, run_dir: Path) -> dict:
    """Полный расчёт для одного отверстия: этап 1 (если нужен) → этап 2. Возвращает run_info."""
    prof = exp.sim["profiles"][opts.profile]
    n1 = int(opts.stage1_events or prof["stage1_events"])
    n2 = int(opts.stage2_events or prof["stage2_events"])
    extra = float(opts.window_extra_mm if opts.window_extra_mm is not None else prof["window_extra_mm"])
    seed = int(opts.seed or exp.sim["run"]["seed"])
    W = 0.5 * hole_um * 1e-3 + extra
    core = 0.5 * hole_um * 1e-3 + prof["core_margin_um"] * 1e-3
    ensure(run_dir)
    stage1, stage2, plane = exp.stage_layers(hole_um, W)
    medium = exp.medium()
    info: dict = {"experiment": exp.id, "hole_um": hole_um, "profile": opts.profile, "upstream": opts.upstream,
                  "environment": environment_info(), "provenance": exp.prov.as_list(),
                  "assumptions": [r.as_dict() for r in exp.prov.assumptions()],
                  "overrides": exp.overrides, "medium": medium}

    analytic = stage1 if opts.upstream == "analytic" else []
    table = source_table(exp, analytic, opts.psi_limit_mrad)
    table_csv = run_dir / "source_table.csv"
    rows = table.write_csv(table_csv, [f"experiment {exp.id}", f"analytic filters: {table.filters}"])
    I_ref = exp.source["current_reference_mA"]
    rate = scan_averaged_fluence_rate(table, exp.source["distance_m"], exp.source["scan_half_amplitude_mm"])
    info["source_table"] = {"file": table_csv.name, "rows": rows, "analytic_filters": table.filters,
                            **table.summary(), "current_reference_mA": I_ref,
                            "psi_edges_mrad": [float(table.psi_edges[0]), float(table.psi_edges[-1])]}

    mats = {l.material for l in stage1 + stage2} | {medium}
    timings = {}
    ps_files: list[str] = []
    w_per_hist_stage1 = None
    if opts.upstream == "stage1":
        # Этап 1 не зависит от размера отверстия → кэшируется по хэшу своей конфигурации
        # (слои, источник, физика, статистика, зерно) и переиспользуется всеми отверстиями.
        z_gen = stage1[0].z_front_mm - 1.0
        hx, hz = _world(stage1, [z_gen, plane], 160.0)
        cfg1 = _base_cfg(exp, f"{exp.id}_stage1", Path("stage1.h5"), n1, seed, opts.threads)
        cfg1.update({
            "world": {"material": medium, "half_xy_mm": hx, "half_z_mm": hz},
            "materials": exp.materials_json(mats),
            "layers": [l.to_json() for l in stage1],
            "scoring": {"pmma_layer": "PMMA", "grids": [], "phase_space_out": True,
                        "phase_space_plane_z_mm": plane, "phase_space_file": "ps"},
            "source": {"mode": "sr_table", "table_file": "source_table.csv", "z_mm": z_gen,
                       "window_half_x_mm": 0.0, "window_half_y_mm": 0.0, **_source_common(exp)},
        })
        cfg1["physics"]["kill_unreachable_electrons"] = True  # на этапе 1 электроны до ПММА не доходят
        cfg1["physics"]["force_collision_roles"] = []       # этап 1 — аналоговый
        key_src = json.dumps(cfg1, sort_keys=True) + table_csv.read_text(encoding="utf-8")
        key = hashlib.sha256(key_src.encode()).hexdigest()[:12]
        d1 = ensure(run_dir.parent / f"_stage1_{key}")
        if not (d1 / "stage1.h5").exists():
            (d1 / "source_table.csv").write_text(table_csv.read_text(encoding="utf-8"), encoding="utf-8")
            cfg1["run"]["output"] = str(d1 / "stage1.h5")
            cfg1["scoring"]["phase_space_file"] = str(d1 / "ps")
            cfg1["source"]["table_file"] = str(d1 / "source_table.csv")
            timings["stage1_s"] = run_liga_sim(cfg1, d1 / "stage1.json", d1 / "stage1.log")
        else:
            print(f"[liga] этап 1: используется кэш {d1}")
            timings["stage1_s"] = 0.0
        import h5py
        with h5py.File(d1 / "stage1.h5", "r") as f:
            a = dict(f["phase_space"].attrs)
        ps_files = sorted(str(p) for p in d1.glob("ps_t*.bin"))
        info["stage1"] = {"events": n1, "records": int(a["records"]), "sum_w": float(a["sum_w"]),
                          "photons_at_plane_per_primary": float(a["sum_w"]) / n1, "dir": str(d1),
                          "layers": [l.to_json() for l in stage1], "plane_z_mm": plane}
        w_per_hist_stage1 = float(a["sum_w"]) / n1
        reuse = n2 / max(int(a["records"]), 1)
        info["stage1"]["reuse_factor"] = reuse
        if reuse > exp.sim.get("max_reuse", 20):
            print(f"[liga] ВНИМАНИЕ: кратность переиспользования фазового пространства {reuse:.0f} > "
                  f"{exp.sim.get('max_reuse', 20)} — оценка погрешности занижена; увеличьте --stage1-events")

    # ---------------------------------------------------------------- этап 2
    d2 = ensure(run_dir / "stage2")
    hx, hz = _world(stage2, [plane - 0.5], W + 3.0)
    cfg2 = _base_cfg(exp, f"{exp.id}_h{hole_um:g}_stage2", d2 / "stage2.h5", n2, seed + 1, opts.threads)
    src2 = {"z_mm": plane, "window_half_x_mm": W, "window_half_y_mm": W, "core_half_x_mm": core,
            "core_half_y_mm": core, "core_fraction": prof["core_fraction"], **_source_common(exp)}
    if opts.upstream == "stage1":
        src2.update({"mode": "phase_space", "phase_space_files": ";".join(ps_files), "ps_n_primaries": n1})
    else:
        src2.update({"mode": "sr_table", "table_file": str(table_csv)})
    sc = exp.sim["scoring"]
    pm_t = [l for l in stage2 if l.role == "pmma"][0].thickness_um
    cfg2.update({
        "world": {"material": medium, "half_xy_mm": hx, "half_z_mm": hz},
        "materials": exp.materials_json({l.material for l in stage2} | {medium}),
        "layers": [l.to_json() for l in stage2],
        "scoring": {"pmma_layer": "PMMA", "grids": scoring_grids(hole_um, sc, pm_t),
                    "spectrum_emin_keV": 0.0, "spectrum_emax_keV": sc["spectrum_emax_keV"],
                    "spectrum_nbins": sc["spectrum_nbins"], "region_margin_um": sc["region_margin_um"]},
        "source": src2,
    })
    timings["stage2_s"] = run_liga_sim(cfg2, d2 / "stage2.json", d2 / "stage2.log")

    # ---------------------------------------------------------------- нормировка
    Q = float(exp.exp["exposure_mA_min"])
    fluence = rate / I_ref * Q * 60.0  # фотоны/мм² (падающий спектр после Be-окон, до Al)
    info["stage2"] = {"events": n2, "window_half_mm": W, "window_area_mm2": 4 * W * W, "core_half_mm": core,
                      "core_fraction": prof["core_fraction"], "layers": [l.to_json() for l in stage2],
                      "plane_z_mm": plane}
    info["normalization"] = {
        "definition": "D_voxel = (sum_w Edep / N_stage2) * Phi_inc * A_window / m_voxel; "
                      "Phi_inc — усреднённый по сканированию флюенс падающего (после Be) спектра.",
        "fluence_rate_per_mA_ph_s_mm2": rate / I_ref,
        "exposure_mA_min": Q,
        "exposure_status": next((r.status for r in exp.prov.records if r.path.endswith("exposure_mA_min")), "?"),
        "incident_fluence_ph_mm2": fluence,
        "window_area_mm2": 4 * W * W,
        "n_histories": n2,
        "stage1_weight_per_history": w_per_hist_stage1,
        "MeV_to_J": MEV_TO_J,
    }
    info["timings"] = timings
    dump_json(info, run_dir / "run_info.json")
    return info

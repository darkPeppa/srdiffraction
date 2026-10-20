"""`liga materials`: коэффициенты ослабления Geant4 (G4EmCalculator) против NIST и составы материалов."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from liga_cli.model import load_experiment
from liga_cli.runner import run_liga_sim
from liga_common.io import dump_json
from plotting.style import SERIES, plt, save

from .materials import mu_rho_nist, transmission

MATS = ["Be", "Al", "Ti", "Au", "GlassyCarbon", "Sapphire", "Kapton", "PMMA", "He_chamber"]
ENERGIES = [3, 4, 5, 6, 7, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 80]


def geant4_xs_table(out: Path, physics: str = "livermore") -> Path:
    exp = load_experiment("be_200", {"physics": {"em": physics}})
    layers, z = [], 0.0
    for m in MATS:
        layers.append({"name": m, "role": "other", "material": m, "thickness_um": 10.0, "z_front_mm": z,
                       "half_x_mm": 1.0, "half_y_mm": 1.0})
        z += 0.1
    cfg = {"run": {"name": "xs", "mode": "xs_table", "n_events": 0, "seed": 1, "threads": 1,
                   "output": str(out / "xs_dummy.h5"), "xs_energies_keV": ENERGIES,
                   "xs_output": str(out / f"geant4_xs_{physics}.csv")},
           "physics": {"em": physics},
           "world": {"material": "Vacuum", "half_xy_mm": 5, "half_z_mm": 5},
           "materials": exp.materials_json(set(MATS) | {"Vacuum"}),
           "layers": layers, "source": {"mode": "pencil", "z_mm": -1}}
    run_liga_sim(cfg, out / f"xs_{physics}.json", out / f"xs_{physics}.log")
    return out / f"geant4_xs_{physics}.csv"


def materials_report(out: Path, physics: str = "livermore") -> dict:
    out.mkdir(parents=True, exist_ok=True)
    exp = load_experiment("be_200")
    M = exp.materials
    # составы и плотности (ТЗ п. 5.2)
    comp = {k: {"density_g_cm3": v.density_g_cm3, "mass_fractions": v.mass_fractions, "state": v.state,
                "pressure_Pa": v.pressure_Pa} for k, v in M.items()}
    dump_json(comp, out / "materials_composition.json")
    rows = []
    for name in M:
        rows.append({"material": name, "density_g_cm3": M[name].density_g_cm3,
                     "composition": ", ".join(f"{el}:{f:.4f}" for el, f in M[name].mass_fractions.items())})
    pd.DataFrame(rows).to_csv(out / "materials_composition.csv", index=False)
    csv = geant4_xs_table(out, physics)
    g4 = pd.read_csv(csv, comment="#")
    res = []
    for m in MATS:
        d = g4[g4.material == m]
        if not M[m].mass_fractions:
            continue
        nist = mu_rho_nist(M[m], d.energy_keV.values)
        for (_, r), mn in zip(d.iterrows(), nist):
            res.append({"material": m, "energy_keV": r.energy_keV, "mu_rho_geant4": r.mu_rho_total_cm2_g,
                        "mu_rho_nist": mn, "rel_diff": r.mu_rho_total_cm2_g / mn - 1,
                        "frac_photo": r.mu_phot_cm / r.mu_total_cm, "frac_compton": r.mu_compt_cm / r.mu_total_cm,
                        "frac_rayleigh": r.mu_rayl_cm / r.mu_total_cm,
                        "electron_csda_range_um": r.electron_csda_range_um})
    df = pd.DataFrame(res)
    df.to_csv(out / f"geant4_vs_nist_{physics}.csv", index=False)
    # критерий: |Δ| < 5% вне ±3% окрестности краёв поглощения (там интерполяция табличных узлов неточна)
    edges = {"Ti": [4.966], "Au": [11.92, 13.73, 14.35], "Al": [1.56], "Sapphire": [1.56]}
    df["near_edge"] = [any(abs(e / ed - 1) < 0.03 for ed in edges.get(m, [])) for m, e in zip(df.material, df.energy_keV)]
    sel = df[(~df.near_edge) & (df.energy_keV >= 5) & (df.energy_keV <= 30)]
    worst = sel.loc[sel.rel_diff.abs().idxmax()]
    summary = {"physics": physics, "max_abs_rel_diff_5_30keV": float(sel.rel_diff.abs().max()),
               "worst": worst.to_dict(), "criterion": "< 0.05", "pass": bool(sel.rel_diff.abs().max() < 0.05)}
    dump_json(summary, out / f"geant4_vs_nist_summary_{physics}.json")
    print(f"  Geant4 ({physics}) vs NIST, 5–30 кэВ: max |Δμ/ρ| = {summary['max_abs_rel_diff_5_30keV']:.1%} "
          f"({worst.material}, {worst.energy_keV} кэВ) → {'OK' if summary['pass'] else 'FAIL'}")
    fig, ax = plt.subplots(figsize=(6.4, 4))
    for k, m in enumerate([x for x in MATS if x != "He_chamber"]):
        d = df[df.material == m]
        ax.plot(d.energy_keV, 100 * d.rel_diff, marker="o", ms=3, color=SERIES[k % 8], label=m)
    ax.axhspan(-5, 5, color="#d9d8d4", alpha=0.4, lw=0)
    ax.set_xscale("log")
    ax.set_xlabel("энергия, кэВ")
    ax.set_ylabel("(μ/ρ)_Geant4 / (μ/ρ)_NIST − 1, %")
    ax.set_title(f"Сверка коэффициентов ослабления: Geant4 {physics} против NIST XCOM", fontsize=9)
    ax.legend(fontsize=7, ncol=2)
    save(fig, out / f"geant4_vs_nist_{physics}")
    # проверка чисел из журнала расхождений
    disc = {
        "Be_200_vs_220_T10keV": [float(transmission(M["Be"], t, [10.0])[0]) for t in (200, 220)],
        "Be_200_vs_220_T5keV": [float(transmission(M["Be"], t, [5.0])[0]) for t in (200, 220)],
        "GlassyC_475_T10keV_rho_1.46_1.52_2.0": [
            float(np.exp(-mu_rho_nist(M["GlassyCarbon"], [10.0])[0] * r * 475e-4)) for r in (1.46, 1.52, 2.0)],
        "Kapton_5um_T_10_6keV": [float(transmission(M["Kapton"], 5, [e])[0]) for e in (10.0, 6.0)],
    }
    dump_json(disc, out / "discrepancy_impacts.json")
    return summary

"""Собирает числа для презентации из results/ в presentation/deck_data.json.

Запуск (нужны numpy и pyyaml): python presentation/prepare_data.py
После нового `./run.sh simulate all` + `./run.sh report` + `./run.sh compare` — перезапустить
этот скрипт и build_deck.js, графики в презентации обновятся.
"""
import csv
import json
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
OUT = Path(__file__).resolve().parent / "deck_data.json"

CONFIGS = [
    ("be_200", "Be 200 мкм"),
    ("carbon_475", "Стеклоуглерод 475 мкм"),
    ("sapphire_contact", "Al₂O₃ 525 мкм, контакт"),
    ("sapphire_280mm", "Al₂O₃ 525 мкм, 280 мм"),
    ("titanium_model", "Ti 2.3 мкм (расчёт)"),
]
# мембрана: материал в таблице сечений Geant4, толщина (мкм)
MEMBRANES = {
    "be_200": ("Be", 200.0),
    "carbon_475": ("GlassyCarbon", 475.0),
    "sapphire_contact": ("Sapphire", 525.0),
    "titanium_model": ("Ti", 2.3),
}
CATEGORIES = [
    ("direct", "прямое"),
    ("membrane_rayleigh_only", "мембрана: рэлей"),
    ("membrane_compton", "мембрана: комптон"),
    ("al_filter_scatter", "Al-фильтр"),
    ("mask_support_scatter", "Ti-основа"),
    ("other_scatter", "Au, каптон, газ"),
    ("pmma_self_scatter", "внутри ПММА"),
    ("external_secondary", "вторичное излучение шаблона"),
]


def pick_runs():
    runs = json.loads((RES / "report" / "all_runs_summary.json").read_text())
    by_exp = {}
    for r in runs:
        # для сравнения материалов берём 300 мкм, иначе ближайшее
        cur = by_exp.get(r["experiment"])
        if cur is None or abs(r["hole_um"] - 300) < abs(cur["hole_um"] - 300):
            by_exp[r["experiment"]] = r
    return by_exp


def xs_table():
    rows = {}
    with open(RES / "materials" / "geant4_xs_livermore.csv") as f:
        lines = [ln for ln in f if not ln.startswith("#")]
    for r in csv.DictReader(lines):
        rows[(r["material"], float(r["energy_keV"]))] = r
    return rows


def nist_mu_rho(material):
    e, mu = [], []
    with open(ROOT / "data" / "reference_data" / "nist_xraymasscoef" / f"{material}.csv") as f:
        for r in csv.DictReader(ln for ln in f if not ln.startswith("#")):
            e.append(float(r["energy_keV"]))
            mu.append(float(r["mu_rho_cm2_g"]))
    e, mu = np.array(e), np.array(mu)
    return lambda x: np.exp(np.interp(np.log(x), np.log(e), np.log(mu)))


def spectrum_series():
    data = np.loadtxt(RES / "spectrum" / "spectrum_flux_power.csv", delimiter=",", comments="#")
    lo, hi, raw, after_be = data[:, 0], data[:, 1], data[:, 2], data[:, 3]
    mu_al = nist_mu_rho("Al")
    rho_al = 2.699
    step = 1.0  # кэВ, ширина точки графика
    edges = np.arange(-0.5, 40.5 + 1e-9, step)  # центры 0, 1, …, 40 кэВ — ровные подписи оси
    centers = 0.5 * (edges[:-1] + edges[1:])
    out = {"energy_keV": [int(round(c)) for c in centers], "series": []}

    def rebin(y):
        idx = np.digitize(0.5 * (lo + hi), edges) - 1
        s = np.array([y[idx == i].sum() for i in range(len(centers))])
        return s / step  # фотоны/(с·мрад·кэВ) при 100 мА

    out["series"].append({"name": "СИ без фильтров", "values": rebin(raw)})
    out["series"].append({"name": "после Be 500 мкм", "values": rebin(after_be)})
    for t_um in (300, 450, 800):
        tr = np.exp(-mu_al(0.5 * (lo + hi)) * rho_al * t_um * 1e-4)
        out["series"].append({"name": f"+ Al {t_um} мкм", "values": rebin(after_be * tr)})
    floor = 1e9
    for s in out["series"]:
        s["values"] = [float(max(v, floor)) for v in s["values"]]
    return out


def main():
    runs = pick_runs()
    xs = xs_table()
    spectra = json.loads((RES / "spectrum" / "experiments_spectra.json").read_text())
    mean_e = {s["experiment"]: s["mean_energy_keV"] for s in spectra}

    configs = []
    for key, label in CONFIGS:
        r = runs[key]
        configs.append({
            "key": key,
            "label": label,
            "hole_um": r["hole_um"],
            "profile": r["profile"],
            "n_histories": r["n_histories"],
            "dose_open": r["edge"]["dose_open_J_cm3"],
            "dose_shadow": r["edge"]["dose_shadow_J_cm3"],
            "width_10_90": r["edge"]["width_10_90_um"],
            "membrane_open_pct": 100 * r["membrane_scatter_fraction"]["open"],
            "membrane_shadow_pct": 100 * r["membrane_scatter_fraction"]["shadow"],
            "shadow_categories_pct": {
                k: 100 * r["category_fractions"]["shadow"].get(k, 0.0) for k, _ in CATEGORIES
            },
            "mean_energy_keV": mean_e.get(key),
        })

    # вероятность рассеяния в мембране при 20 кэВ (тонкий слой, первое взаимодействие)
    why = []
    for key, (mat, t_um) in MEMBRANES.items():
        r = xs[(mat, 20.0)]
        d_cm = t_um * 1e-4
        why.append({
            "key": key,
            "material": mat,
            "thickness_um": t_um,
            "mass_thickness_mg_cm2": 1e3 * float(r["density_g_cm3"]) * d_cm,
            "p_rayleigh_pct": 100 * float(r["mu_rayl_cm"]) * d_cm,
            "p_compton_pct": 100 * float(r["mu_compt_cm"]) * d_cm,
            "transmission_pct": 100 * float(np.exp(-float(r["mu_total_cm"]) * d_cm)),
        })

    sup = yaml.safe_load((ROOT / "data" / "experimental_profiles" / "supervisor_profiles.yaml").read_text())
    approx = {}
    for key, v in sup.items():
        approx[key] = [
            {"hole_um": p["hole_um"], "width_10_90": (p.get("derived") or {}).get("width_10_90"), "b": p.get("b")}
            for p in v["profiles"] if p.get("formula_present")
        ]

    runs_all = []
    for r in json.loads((RES / "report" / "all_runs_summary.json").read_text()):
        runs_all.append({
            "key": r["experiment"],
            "hole_um": r["hole_um"],
            "width_10_90": r["edge"]["width_10_90_um"],
            "dose_open": r["edge"]["dose_open_J_cm3"],
            "dose_shadow": r["edge"]["dose_shadow_J_cm3"],
            "membrane_open_pct": 100 * r["membrane_scatter_fraction"]["open"],
            "membrane_shadow_pct": 100 * r["membrane_scatter_fraction"]["shadow"],
        })
    runs_all.sort(key=lambda r: ([k for k, _ in CONFIGS].index(r["key"]), r["hole_um"]))

    # Geant4 + феноменологическое проявление (compare-geant4): ширины края с боковым проявлением
    dev = json.loads((RES / "interferometry" / "geant4_vs_experiment.json").read_text())
    dev_w = [p["lateral"]["transition_10_90_um"] for r in dev["rows"] for p in r["predictions"]]

    data = {
        "configs": configs,
        "runs_all": runs_all,
        "development_lateral_width_um": [min(dev_w), max(dev_w)],
        "categories": [{"key": k, "label": l} for k, l in CATEGORIES],
        "why_20keV": why,
        "spectrum": spectrum_series(),
        "approximations": approx,
        "source_parameters": json.loads((RES / "spectrum" / "source_parameters.json").read_text()),
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=float))
    print(f"записано {OUT}")


if __name__ == "__main__":
    main()

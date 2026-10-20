"""Geant4 + модель проявления ↔ экспериментальные профили (только относительные тенденции).

Без калибровки R(D) и горизонтального масштаба снимков количественное сравнение
невозможно. Модуль строит предсказанные профили растворения по расчётной дозе для
семейства феноменологических параметров и сопоставляет их НОРМИРОВАННЫЕ формы и
ширины переходов (мкм) с аппроксимациями техзаданий (единицы которых не подтверждены).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from analysis.io import load_run
from analysis.run_analysis import find_runs
from comparison import supervisor_profiles as sp
from liga_common.io import dump_json
from plotting.style import SERIES, TEXT2, plt, save

from .development_forward import lateral_profile, rate_sigmoid, resample_uniform, vertical_depth
from analysis.dose import transition_width


def dose_xz(run, hole):
    """D(n, z) поперёк края (свёрнуто по двум краям), n — от края, мкм; Дж/см³."""
    g = run.grids["edge_strip"]
    V = g.volumes_cm3()[:, 0, :]
    E = g.edep[:, 0, :]
    n = np.abs(g.xc) - hole / 2
    key = np.round(n, 6)
    u = np.unique(key)
    D = np.vstack([E[key == k].sum(0) / V[key == k].sum(0) for k in u]) * run.scale_J
    return u, D, g.z


def compare_geant4(runs_root: Path, out: Path, t_dev_s: float = 60.0) -> list[dict]:
    sup = sp.load()
    rows = []
    infos = [(rd, json.loads((rd / "run_info.json").read_text(encoding="utf-8"))) for rd in find_runs(runs_root)]
    infos.sort(key=lambda t: (t[1]["experiment"], float(t[1]["hole_um"]), str(t[0])))
    for rd, info in infos:
        exp, hole = info["experiment"], float(info["hole_um"])
        run = load_run(rd)
        n, D, z = dose_xz(run, hole)
        # сглаживание статистического шума по n (окно 1 мкм) для устойчивости модели проявления
        from scipy.ndimage import uniform_filter1d
        step = 0.25
        nu, Du = resample_uniform(n, D, step)
        Du = uniform_filter1d(Du, size=4, axis=0)
        d_open = float(np.median(Du[nu < -min(3.0, hole / 4)].mean(axis=1))) if (nu < -min(3.0, hole / 4)).any() \
            else float(Du.max())
        preds = []
        fig, ax = plt.subplots(figsize=(6.4, 4.0))
        for k, frac in enumerate([0.3, 0.6, 0.9]):
            d50 = frac * d_open
            rate = lambda X, d50=d50: rate_sigmoid(X, 0.0, 15.0 / t_dev_s * 1.2, d50, 0.08 * d50)
            dv = vertical_depth(Du, z, rate, t_dev_s)
            dl, _ = lateral_profile(Du, nu, z, rate, t_dev_s)
            # один край: n < 0 — под окном (растворено), n > 0 — под золотом
            inner = -min(10.0, hole / 4.0)  # плато под окном: для малых окон ближе к краю

            def robust(depth):
                o = float(np.median(depth[nu < inner])) if (nu < inner).any() else np.nan
                sh = float(np.median(depth[nu > 20])) if (nu > 20).any() else np.nan
                w = transition_width(nu, depth, o, sh)[0] if o > sh else np.nan
                return {"depth_open_um": o, "depth_shadow_um": sh, "transition_10_90_um": w,
                        "open_depth_rel_spread": float(np.std(depth[nu < inner]) / o) if o > 0 else np.nan}
            mv, ml = robust(dv), robust(dl)
            preds.append({"d50_over_dose_open": frac, "vertical": mv, "lateral": ml})
            ax.plot(nu, dv, color=SERIES[k], ls="--", label=f"вертикальная, D50={frac:.1f}·D_open")
            ax.plot(nu, dl, color=SERIES[k], label=f"с боковым проявлением, D50={frac:.1f}·D_open")
        ax.axvline(0, color=TEXT2, lw=0.8, ls=":")
        ax.invert_yaxis()
        ax.set_xlabel("n — расстояние от края окна Au, мкм")
        ax.set_ylabel("глубина растворения, мкм")
        ax.set_title(f"{exp}, {hole:g} мкм: Geant4 + феноменологическая R(D) (НЕ откалибрована), t=60 с", fontsize=8)
        ax.legend(fontsize=6)
        save(fig, out / "geant4_development" / f"{exp}_{hole:g}um")
        row = {"run": rd.name, "experiment": exp, "hole_um": hole, "dose_open_J_cm3": d_open, "predictions": preds}
        if exp in sup:
            for p in sup[exp]["profiles"]:
                if abs(p["hole_um"] - hole) < 1e-6 and p.get("derived"):
                    row["supervisor_width_10_90"] = p["derived"]["width_10_90"]
        rows.append(row)
        print(f"  {exp} {hole:g} мкм: предсказанные ширины перехода (боковая модель) = "
              f"{[(round(pp['lateral']['transition_10_90_um'], 2), round(pp['lateral']['depth_open_um'], 1),
                round(pp['lateral']['open_depth_rel_spread'], 2)) for pp in preds]} мкм; "
              f"(ширина, глубина под окном, относит. разброс глубины); аппроксимация ТЗ: "
              f"{row.get('supervisor_width_10_90')}")
    dump_json({"rows": rows, "status": "relative_only: R(D) не откалиброван, масштаб снимков не подтверждён"},
              out / "geant4_vs_experiment.json")
    return rows

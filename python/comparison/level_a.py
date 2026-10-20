"""Сравнение уровня A (ТЗ п. 9.3): относительные характеристики края при явных допущениях.

Сравниваются НЕ доза и рельеф напрямую, а ширины переходных областей:
  • ширина 10–90 % дозового профиля поперёк края (Geant4);
  • ширина 10–90 % аппроксимации профиля углубления из техзадания (Δn ≈ 1.035·a·50/K2);
  • для иллюстрации — ширина нормированного профиля «глубины проявления» при
    феноменологической зависимости скорости растворения R ∝ D^p (p = 1…4) и
    отсутствии насыщения (глубина ∝ R·t). Это НЕ откалиброванная модель: калибровки
    R(D) для данного ПММА и проявителя нет (см. docs/comparison.md).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from analysis.dose import edge_profile, plateau_levels, transition_width
from analysis.io import load_run
from analysis.run_analysis import find_runs
from liga_common.io import dump_json
from plotting.style import SERIES, TEXT2, plt, save

from . import supervisor_profiles as sp

POWERS = [1, 2, 3, 4]


def _width_of_mapping(n, D, d_open, d_shadow, p):
    """Ширина 10–90 % профиля (D/D_open)^p (вертикальная модель проявления без насыщения)."""
    y = np.clip(D / d_open, 0, None) ** p
    y_open = 1.0
    y_sh = (d_shadow / d_open) ** p
    return transition_width(n, y, y_open, y_sh)[0]


def compare_all(runs_root: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    sup = sp.load()
    rows = []
    infos = [(rd, json.loads((rd / "run_info.json").read_text(encoding="utf-8"))) for rd in find_runs(runs_root)]
    infos.sort(key=lambda t: (t[1]["experiment"], float(t[1]["hole_um"]), str(t[0])))
    for rd, info in infos:
        exp, hole = info["experiment"], float(info["hole_um"])
        run = load_run(rd)
        n, D, S = edge_profile(run, hole, rebin_rel_err=0.05)
        d_open, d_shadow = plateau_levels(n, D, hole)
        w_dose = transition_width(n, D, d_open, d_shadow)[0]
        row = {"run": str(rd.relative_to(runs_root)), "experiment": exp, "hole_um": hole, "profile": info["profile"],
               "upstream": info["upstream"], "n_histories": run.n, "dose_open_J_cm3": d_open,
               "dose_shadow_J_cm3": d_shadow, "contrast": d_open / d_shadow if d_shadow > 0 else None,
               "dose_width_10_90_um": w_dose,
               "developed_width_10_90_um_powerlaw": {f"p={p}": _width_of_mapping(n, D, d_open, d_shadow, p)
                                                    for p in POWERS}}
        prof = None
        if exp in sup:
            for p in sup[exp]["profiles"]:
                if abs(p["hole_um"] - hole) < 1e-6:
                    prof = p
        if prof is not None and prof.get("derived"):
            row["supervisor"] = {"a": prof["a"], "b": prof["b"], "c": prof["c"], "K1": prof["K1"], "K2": prof["K2"],
                                 "width_10_90": prof["derived"]["width_10_90"], "rendered": prof["rendered"],
                                 "status": prof["status"]}
        elif prof is not None:
            row["supervisor"] = {"a": prof["a"], "b": prof["b"], "c": prof["c"], "note": prof["notes"]}
        else:
            row["supervisor"] = None
        rows.append(row)
        print(f"  {exp:18s} {hole:5g} мкм: ширина дозы 10–90% = {w_dose:.3g} мкм; "
              f"руководитель: {row['supervisor'].get('width_10_90', float('nan')) if row['supervisor'] else 'нет данных'}")
    dump_json({"rows": rows, "limitations": [
        "Профиль углубления ≠ профиль дозы; без калибровки R(D) сравниваются только ширины переходов.",
        "Единицы h и поперечной координаты n в аппроксимациях не подтверждены (b до 112 при ПММА 15 мкм).",
        "Связь изображений интерферограмм с отверстиями не подтверждена (см. results/interferometry).",
        "Доза под отверстием (0.5–1.3 кДж/см³) ниже табличной минимальной дозы ПММА 2 кДж/см³ (диссертация, табл. 4)."]},
        out / "level_a_comparison.json")
    # график: ширины по отверстиям
    if rows:
        fig, ax = plt.subplots(figsize=(7.0, 4.2))
        exps = sorted({r["experiment"] for r in rows})
        for k, e in enumerate(exps):
            rr = sorted((r for r in rows if r["experiment"] == e), key=lambda r: r["hole_um"])
            h = [r["hole_um"] for r in rr]
            ax.plot(h, [r["dose_width_10_90_um"] for r in rr], marker="o", color=SERIES[k], label=f"{e}: доза (Geant4)")
            hs = [r["hole_um"] for r in rr if r["supervisor"] and "width_10_90" in r["supervisor"]]
            ws = [r["supervisor"]["width_10_90"] for r in rr if r["supervisor"] and "width_10_90" in r["supervisor"]]
            if hs:
                ax.plot(hs, ws, marker="s", ls="--", color=SERIES[k], label=f"{e}: аппроксимация ТЗ")
        ax.set_xscale("log")
        ax.set_xlabel("размер отверстия, мкм")
        ax.set_ylabel("ширина перехода 10–90 %, мкм")
        ax.set_title("Уровень A: ширина края — дозовый профиль vs аппроксимации профиля углубления\n"
                     "(разные физические величины; единицы аппроксимаций не подтверждены)", fontsize=8)
        ax.legend(fontsize=6, ncol=2)
        save(fig, out / "level_a_widths")
    # графики аппроксимаций руководителя (как есть, в их собственных координатах)
    for exp, v in sup.items():
        fig, ax = plt.subplots(figsize=(6.4, 4.0))
        k = 0
        for p in v["profiles"]:
            if not p.get("derived"):
                continue
            n0 = p["derived"]["edge_position_n0"]
            nn = np.linspace(n0 - 40, n0 + 40, 400)
            ax.plot(nn - n0, sp.h_of_n(p, nn), color=SERIES[k % 8], label=f"{p['hole_um']:g} мкм: {p['rendered']}")
            k += 1
        ax.axvline(0, color=TEXT2, lw=0.8, ls="--")
        ax.set_xlabel("n − n0 (заявлено: мкм)")
        ax.set_ylabel("h (единицы не подтверждены)")
        ax.set_title(f"Аппроксимации профиля края из техзадания: {exp}", fontsize=9)
        ax.legend(fontsize=5)
        save(fig, out / f"supervisor_profiles_{exp}")
    return {"rows": rows}

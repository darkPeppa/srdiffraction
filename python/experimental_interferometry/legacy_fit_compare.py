"""Независимая проверка аппроксимаций профилей научного руководителя.

Формулы извлекаются заново из исходных DOCX (comparison.docx_formulas) — не из
перепечатанных коэффициентов. Проверяются внутренняя согласованность и физическая
правдоподобность; сопоставление с изображением возможно только при подтверждённой
атрибуции кадра и горизонтальной калибровке, иначе вердикт — unverifiable.
Вердикты: validated | conditionally_validated | discrepant | unverifiable.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from comparison import supervisor_profiles as sp
from liga_common.io import dump_json
from plotting.style import SERIES, TEXT2, plt, save

PMMA_UM = 15.0


def checks_for(exp: str, p: dict) -> dict:
    flags = []
    if not p.get("formula_present"):
        return {"verdict": "unverifiable", "reasons": ["в таблице техзадания нет формулы для этого отверстия"],
                "flags": ["missing_formula"]}
    d = p["derived"]
    reasons = []
    if p["b"] > PMMA_UM:
        flags.append("step_exceeds_pmma_thickness")
        reasons.append(f"высота ступеньки b={p['b']} > толщины ПММА {PMMA_UM} мкм — h не может быть глубиной в мкм; "
                       "вероятно, h — смещение полос в пикселях/делениях или единицы иные")
    if p["offset_d"] > PMMA_UM:
        flags.append("offset_exceeds_pmma_thickness")
        reasons.append(f"смещение d={p['offset_d']} > 15 мкм — h в иных единицах или со сдвигом начала отсчёта")
    if p["K1"] != 100 or p["K2"] != 50:
        flags.append("nonstandard_coordinate_scaling")
        reasons.append(f"масштабирование координат K1={p['K1']:g}, K2={p['K2']:g} отличается от типового 100/50 — "
                       "координатные преобразования различаются между кадрами")
    if p["sign"] < 0:
        flags.append("inverted_sign")
        reasons.append("знак перед b отрицательный — ориентация профиля (левый/правый край) иная")
    if d["width_10_90"] < 0.5:
        flags.append("subresolution_width")
        reasons.append(f"ширина перехода {d['width_10_90']:.2f} мкм ниже оптического разрешения (~0.5–1 мкм) — "
                       "вероятно, недооценена или определена по единичным точкам")
    reasons.append("нет подтверждённой атрибуции изображения ↔ отверстия и горизонтальной калибровки — "
                   "сравнение с исходным кадром невозможно")
    return {"verdict": "unverifiable", "reasons": reasons, "flags": flags,
            "width_10_90": d["width_10_90"], "edge_position_n0": d["edge_position_n0"]}


def validate_supervisor_profiles(out: Path) -> dict:
    data = sp.build_yaml()
    rows = []
    for exp, v in data.items():
        for p in v["profiles"]:
            c = checks_for(exp, p)
            rows.append({"experiment": exp, "hole_um": p["hole_um"], "a": p["a"], "b": p["b"], "c": p["c"],
                         "formula": p["rendered"], "source_object": p["source_object"], **c})
        for w in v["warnings"]:
            rows.append({"experiment": exp, "hole_um": None, "verdict": "unverifiable",
                         "reasons": [w], "flags": ["orphan_formula_object"]})
    dump_json(rows, out / "supervisor_validation.json")
    # сводная проверка единиц: b vs 15 мкм
    n_b = sum("step_exceeds_pmma_thickness" in r.get("flags", []) for r in rows)
    print(f"  аппроксимаций: {sum(r['hole_um'] is not None for r in rows)}; с b > 15 мкм: {n_b}; "
          f"«осиротевших» формул: {sum('orphan_formula_object' in r.get('flags', []) for r in rows)}; "
          "вердикт по всем: unverifiable (нет атрибуции и калибровки X)")
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    for k, exp in enumerate(data):
        rr = [r for r in rows if r["experiment"] == exp and r.get("width_10_90")]
        ax.plot([r["hole_um"] for r in rr], [r["width_10_90"] for r in rr], marker="o", color=SERIES[k], label=exp)
    ax.set_xscale("log")
    ax.set_xlabel("номинальный размер отверстия, мкм")
    ax.set_ylabel("ширина 10–90 % аппроксимации (заявлено: мкм)")
    ax.set_title("Аппроксимации руководителя: ширина перехода (единицы не подтверждены)", fontsize=9)
    ax.legend(fontsize=7)
    save(fig, out / "supervisor_widths")
    return {"rows": rows}

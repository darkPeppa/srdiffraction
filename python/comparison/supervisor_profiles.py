"""Аппроксимации профилей края из техзаданий: извлечение, производные метрики, YAML.

h(n) = s·(b/π)·atan[k·(K1·c/K2 − n)] + d,  k = 2π·scale·K2/(denom·a)
  • положение края (центр ступеньки):  n0 = K1·c/K2
  • высота ступеньки:                    b   (от d − b/2 до d + b/2)
  • ширина 10–90 % по координате n:      Δn = 2·tan(0.4π)/k ≈ 1.035·a·(50/K2)
Единицы h и смысл b/d в документах не определены однозначно («все переменные
в микронах», но b до 112 при толщине ПММА 15 мкм) — см. docs/comparison.md.
Поэтому для сравнения используется только поперечная ширина перехода Δn
(при условии, что n действительно в мкм) — статус unverified.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import yaml

from liga_common.paths import DATA

from .docx_formulas import extract_all

YAML_PATH = DATA / "experimental_profiles" / "supervisor_profiles.yaml"
DOC_DIR = DATA / "source_documents" / "masks_techzadania"


def derived(p: dict) -> dict:
    if not p.get("formula_present") or p.get("K2") is None:
        return {}
    k = 2 * math.pi * p["scale"] * p["K2"] / (p["denom"] * p["a"])
    return {"edge_position_n0": p["K1"] * p["c"] / p["K2"], "step_height_b": p["b"],
            "slope_k_per_um": k, "width_10_90": 2 * math.tan(0.4 * math.pi) / k,
            "max_slope": p["b"] / math.pi * k}


def h_of_n(p: dict, n):
    n = np.asarray(n, float)
    k = 2 * math.pi * p["scale"] / (p["denom"] * p["a"])
    return p["sign"] * p["b"] / math.pi * np.arctan(k * (p["K1"] * p["c"] - p["K2"] * n)) + p["offset_d"]


def build_yaml(path: Path = YAML_PATH) -> dict:
    data = extract_all(DOC_DIR)
    for exp, v in data.items():
        for p in v["profiles"]:
            p["derived"] = derived(p)
            p["status"] = {"formula": "document (извлечено из OLE/WMF таблицы DOCX)" if p["formula_present"]
                           else "unknown (формулы в таблице нет)",
                           "units_of_h": "unverified", "lateral_units_n": "unverified (заявлено: мкм)",
                           "attribution_to_image": "unknown"}
    header = ("# СГЕНЕРИРОВАНО автоматически: python -m comparison.supervisor_profiles (не редактировать вручную)\n"
              "# Источник: таблицы DOCX data/source_documents/masks_techzadania; формулы — объекты MathType (WMF-превью).\n"
              "# h(n) = sign·(b/π)·atan[2π·scale·(K1·c − K2·n)/(denom·a)] + offset_d\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return data


def load(path: Path = YAML_PATH) -> dict:
    if not path.exists():
        return build_yaml(path)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    d = build_yaml()
    for e, v in d.items():
        for p in v["profiles"]:
            dd = p["derived"]
            print(e, p["hole_um"], f"width10-90={dd.get('width_10_90', float('nan')):.3g}", p["rendered"] or p["notes"])

"""Единый стиль графиков (PNG + PDF).

Категориальные цвета — фиксированный порядок (никогда не циклический), одна ось Y
на график, последовательные карты — один тон светлый→тёмный, подписи — цветом текста.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
TEXT = "#0b0b0b"
TEXT2 = "#52514e"
GRID = "#d9d8d4"
SEQ = "Blues"        # величина (доза)
SEQ_FRAC = "Oranges"  # доли (0..1)


def apply():
    plt.rcParams.update({
        "figure.dpi": 120, "savefig.dpi": 200, "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
        "axes.edgecolor": TEXT2, "axes.labelcolor": TEXT, "xtick.color": TEXT2, "ytick.color": TEXT2,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False,
        "axes.spines.right": False, "lines.linewidth": 1.6, "legend.frameon": False, "font.family": "DejaVu Sans",
        "axes.prop_cycle": matplotlib.cycler(color=SERIES),
    })


def save(fig, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


apply()

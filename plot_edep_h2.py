#!/usr/bin/env python3
"""
Plot Geant4 H2 CSV (tools::histo::h2d) as a heatmap.

Usage:
  python3 plot_edep_h2.py \
      --input build/energy_deposition_pmma_h2_Edep_2D.csv \
      --output build/energy_deposition_pmma_h2_Edep_2D.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def parse_axis_lines(lines: list[str]) -> tuple[int, float, float, int, float, float]:
    """Extract x/y axis setup from Geant4 metadata lines."""
    axis_lines = [line.strip() for line in lines if line.startswith("#axis fixed")]
    if len(axis_lines) < 2:
        raise ValueError("Could not find two '#axis fixed ...' lines in input file.")

    def parse_one(axis_line: str) -> tuple[int, float, float]:
        parts = axis_line.split()
        # Expected: #axis fixed <nbins> <min> <max>
        if len(parts) != 5:
            raise ValueError(f"Unexpected axis metadata format: {axis_line}")
        nbins = int(parts[2])
        xmin = float(parts[3])
        xmax = float(parts[4])
        return nbins, xmin, xmax

    xbins, xmin, xmax = parse_one(axis_lines[0])
    ybins, ymin, ymax = parse_one(axis_lines[1])
    return xbins, xmin, xmax, ybins, ymin, ymax


def load_h2_sw_matrix(csv_path: Path) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """
    Load Sw from H2 CSV and return active-bin matrix and plotting extent.

    Geant4 H2 CSV stores (nbins+2) x (nbins+2) bins because of under/overflow.
    We remove 1-bin border to keep only physical bin area.
    """
    text = csv_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    xbins, xmin, xmax, ybins, ymin, ymax = parse_axis_lines(lines)

    df = pd.read_csv(csv_path, comment="#")
    if "Sw" not in df.columns:
        raise ValueError("Column 'Sw' not found in CSV.")

    values = df["Sw"].to_numpy(dtype=float)
    expected_with_flow = (xbins + 2) * (ybins + 2)
    if values.size != expected_with_flow:
        raise ValueError(
            f"Unexpected number of bins: got {values.size}, expected {expected_with_flow}."
        )

    # Geant4 dumps bins in one-dimensional order.
    # Reshape to 2D including under/overflow bins.
    matrix_with_flow = values.reshape((ybins + 2, xbins + 2))

    # Remove under/overflow rows/columns.
    matrix = matrix_with_flow[1:-1, 1:-1]
    extent = (xmin, xmax, ymin, ymax)
    return matrix, extent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plot Geant4 H2 CSV as heatmap.")
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to Geant4 H2 CSV, e.g. energy_deposition_pmma_h2_Edep_2D.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("h2_heatmap.png"),
        help="Output image path (default: h2_heatmap.png).",
    )
    parser.add_argument(
        "--log",
        action="store_true",
        help="Use log color scale (log10(1 + value)).",
    )
    parser.add_argument(
        "--cmap",
        default="inferno",
        help="Matplotlib colormap (default: inferno).",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    matrix, extent = load_h2_sw_matrix(args.input)
    z = np.log10(1.0 + matrix) if args.log else matrix

    plt.figure(figsize=(7.5, 6.2), dpi=140)
    im = plt.imshow(
        z,
        origin="lower",
        extent=extent,
        interpolation="nearest",
        cmap=args.cmap,
        aspect="equal",
    )
    cbar = plt.colorbar(im)
    cbar.set_label("log10(1 + Sw)" if args.log else "Sw (sum of deposited energy, keV)")

    plt.xlabel("X position [mm]")
    plt.ylabel("Y position [mm]")
    plt.title("Energy deposition in PMMA (H2)")
    plt.tight_layout()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(args.output)
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()

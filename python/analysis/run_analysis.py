"""Анализ одного прогона: сводка (JSON/CSV) и графики."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from liga_common.io import dump_json
from plotting import style
from plotting.style import SERIES, plt, save

from .dose import depth_integrated, edge_profile, plateau_levels, region_fraction, transition_width
from .io import Run, load_run

# Сводные группы категорий для графиков (≤ 6 серий, фиксированный порядок цветов)
GROUPS = [
    ("прямое излучение", ["direct"]),
    ("рассеяние в мембране (рэлей)", ["membrane_rayleigh_only"]),
    ("рассеяние в мембране (комптон)", ["membrane_compton"]),
    ("вторичное излучение вне ПММА", ["external_secondary"]),
    ("рассеяние в Al/Be/Ti/Au/каптоне", ["al_filter_scatter", "be_window_scatter", "mask_support_scatter",
                                         "other_scatter"]),
    ("рассеяние внутри ПММА", ["pmma_self_scatter"]),
]


def category_profile_map(run: Run, hole: float, cats: list[str]):
    """Профиль дозы категорий по карте map3d: полосы вдоль четырёх краёв (без углов), по глубине суммарно."""
    g = run.grids["map3d"]
    V = g.volumes_cm3()
    idx = [g.cat_names.index(c) for c in cats]
    E = sum(g.cat[i] for i in idx)
    h2 = hole / 2
    X, Y = np.meshgrid(g.xc, g.yc, indexing="ij")
    band = h2 - min(10.0, h2 / 2)
    # расстояние до края по x для |y|<band и по y для |x|<band
    nx = np.abs(X) - h2
    ny = np.abs(Y) - h2
    Es, Vs = E.sum(axis=2), V.sum(axis=2)
    keys, e_acc, v_acc = {}, {}, {}
    for nn, sel in ((nx, np.abs(Y) < band), (ny, np.abs(X) < band)):
        for k, e, v in zip(np.round(nn[sel], 6), Es[sel], Vs[sel]):
            e_acc[k] = e_acc.get(k, 0.0) + e
            v_acc[k] = v_acc.get(k, 0.0) + v
    ks = np.array(sorted(e_acc))
    ev = np.array([e_acc[k] for k in ks])
    vv = np.array([v_acc[k] for k in ks])
    # укрупнение для читаемости: 2 мкм у края (|n|<20), 5 мкм дальше; края ячеек не пересекают n=0
    lo, hi = ks.min(), ks.max()
    edges = np.unique(np.r_[np.arange(np.floor(lo / 5) * 5, -20, 5), np.arange(-20, 20, 2), np.arange(20, hi + 5, 5)])
    idx = np.digitize(ks, edges)
    nb, Eb, Vb = [], [], []
    for b in np.unique(idx):
        m = idx == b
        nb.append((ks[m] * vv[m]).sum() / vv[m].sum()); Eb.append(ev[m].sum()); Vb.append(vv[m].sum())
    return np.array(nb), np.array(Eb) * run.scale_J / np.array(Vb)


def find_runs(root: Path) -> list[Path]:
    return sorted(p.parent for p in Path(root).rglob("run_info.json") if (p.parent / "stage2" / "stage2.h5").exists())


def summarize(run: Run) -> dict:
    hole = float(run.info["hole_um"])
    g = run.grids["map3d"]
    out = {"experiment": run.info["experiment"], "hole_um": hole, "profile": run.info["profile"],
           "upstream": run.info["upstream"], "n_histories": run.n, "physics": run.meta.get("physics_em"),
           "wall_time_s": run.meta.get("wall_time_s")}
    # ---- профиль края (глубинно-усреднённый) и по слоям; ячейки сливаются до погрешности ≤ 5%
    n, D, S = edge_profile(run, hole, rebin_rel_err=0.05)
    d_open, d_shadow = plateau_levels(n, D, hole)
    w, n90, n10 = transition_width(n, D, d_open, d_shadow)
    out["edge"] = {"dose_open_J_cm3": d_open, "dose_shadow_J_cm3": d_shadow,
                   "contrast_open_to_shadow": d_open / d_shadow if d_shadow > 0 else None,
                   "width_10_90_um": w, "n90_um": n90, "n10_um": n10,
                   "note": "n — расстояние от края отверстия; <0 под отверстием, >0 под золотом"}
    zl = run.grids["edge_strip"].z
    by_depth = []
    for z0 in range(0, int(round(zl[-1])), 3):
        nz, Dz, _ = edge_profile(run, hole, z_range=(z0, z0 + 3), rebin_rel_err=0.1)
        o, s = plateau_levels(nz, Dz, hole)
        wz = transition_width(nz, Dz, o, s)[0]
        by_depth.append({"z_um": [z0, z0 + 3], "dose_open_J_cm3": o, "dose_shadow_J_cm3": s, "width_10_90_um": wz})
    out["edge_by_depth"] = by_depth
    # ---- доли рассеяния
    out["membrane_scatter_fraction"] = region_fraction(run, hole, "membrane_any_scatter")
    out["any_scatter_fraction"] = region_fraction(run, hole, "any_scatter_outside_pmma")
    out["membrane_rayleigh_fraction"] = region_fraction(run, hole, "membrane_rayleigh")
    out["membrane_compton_fraction"] = region_fraction(run, hole, "membrane_compton")
    # ---- разложение по непересекающимся категориям (регионы open/edge/shadow)
    rc = run.spectra["region_edep_by_category_MeV"]
    names = run.spectra["category_names"].split(",")
    out["category_fractions"] = {reg: {nm: float(rc[i, k] / rc[i].sum()) if rc[i].sum() > 0 else None
                                       for k, nm in enumerate(names)}
                                 for i, reg in enumerate(["open", "edge", "shadow"])}
    out["decomposition_closure"] = float(abs(g.cat.sum() - g.edep.sum()) / max(g.edep.sum(), 1e-300))
    # ---- глубинная доза (open/shadow)
    V = g.volumes_cm3()
    X, Y = np.meshgrid(g.xc, g.yc, indexing="ij")
    h2 = hole / 2
    m = min(5.0, h2 / 2)
    op = (np.abs(X) < h2 - m) & (np.abs(Y) < h2 - m)
    sh = (np.abs(X) > h2 + 20) | (np.abs(Y) > h2 + 20)
    out["depth_dose"] = {"z_um": g.zc.tolist(),
                         "open_J_cm3": (g.edep[op].sum(0) * run.scale_J / V[op].sum(0)).tolist(),
                         "shadow_J_cm3": (g.edep[sh].sum(0) * run.scale_J / V[sh].sum(0)).tolist()}
    # ---- энергия первичных фотонов, формирующих дозу
    e = run.spectra["e_edges_keV"]
    ec = 0.5 * (e[1:] + e[:-1])
    ed = run.spectra["edep_by_primary_energy_MeV"]
    out["mean_primary_energy_of_dose_keV"] = {r: float((ed[i] * ec).sum() / ed[i].sum()) if ed[i].sum() > 0 else None
                                             for i, r in enumerate(["open", "edge", "shadow"])}
    # ---- баланс энергии
    b = run.balance
    acc = b["edep_by_role_MeV"].sum() + b["e_escape_MeV"] + b["e_killed_stack_MeV"] + b["e_killed_plane_MeV"]
    out["energy_balance_rel_error"] = float(abs(acc - b["e_incident_MeV"]) / b["e_incident_MeV"])
    out["normalization"] = run.info["normalization"]
    out["units"] = {"dose": "J/cm3 (×1/ρ_PMMA·1e3 → Gy); 1 кДж/см³ = 1000 J/cm3",
                    "density_pmma_g_cm3": run.density_g_cm3}
    return out


def plots(run: Run, outdir: Path, s: dict) -> None:
    hole = float(run.info["hole_um"])
    title = f"{run.info['experiment']}, отверстие {hole:g} мкм ({run.info['profile']}, N={run.n:.2g})"
    g = run.grids["map3d"]
    # 1. карта дозы (усреднённая по глубине), log
    Dxy = depth_integrated(run)
    fig, ax = plt.subplots(figsize=(5.2, 4.4))
    pos = Dxy[Dxy > 0]
    vmin = pos.min() if pos.size else 1
    from matplotlib.colors import LogNorm
    im = ax.pcolormesh(g.x, g.y, np.where(Dxy > 0, Dxy, np.nan).T, cmap=style.SEQ,
                       norm=LogNorm(vmin=max(vmin, Dxy.max() * 1e-4), vmax=Dxy.max()), shading="flat")
    ax.set_aspect("equal")
    ax.set_xlabel("x, мкм")
    ax.set_ylabel("y, мкм")
    ax.set_title("Доза в ПММА (среднее по 15 мкм)\n" + title, fontsize=8)
    fig.colorbar(im, ax=ax, label="Дж/см³")
    ax.grid(False)
    save(fig, outdir / "dose_map_xy")
    # 2. карта доли дозы от историй с рассеянием в мембране
    fi = g.feat_names.index("membrane_any_scatter")
    Ef = g.feat[fi].sum(axis=2)
    Et = g.edep.sum(axis=2)
    frac = np.where(Et > 0, Ef / np.where(Et > 0, Et, 1), np.nan)
    fig, ax = plt.subplots(figsize=(5.2, 4.4))
    im = ax.pcolormesh(g.x, g.y, frac.T, cmap=style.SEQ_FRAC, vmin=0, vmax=np.nanmax(frac) if np.isfinite(frac).any() else 1)
    ax.set_aspect("equal")
    ax.set_xlabel("x, мкм")
    ax.set_ylabel("y, мкм")
    ax.set_title("Доля дозы от историй с рассеянием в мембране\n" + title, fontsize=8)
    fig.colorbar(im, ax=ax, label="доля")
    ax.grid(False)
    save(fig, outdir / "membrane_scatter_fraction_xy")
    # 3. профиль поперёк края: полный и по группам категорий
    n, D, S = edge_profile(run, hole, rebin_rel_err=0.05)
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    pos = D > 0
    ax.errorbar(n[pos], D[pos], yerr=S[pos], fmt="o-", ms=2.5, lw=1.2, elinewidth=0.8, color=SERIES[0],
                label="полная доза (±1σ)")
    g = run.grids["map3d"]
    # Категории — по карте map3d (больше статистики): полоса вдоль краёв, сложение по глубине
    for k, (lab, cats) in enumerate(GROUPS, start=0):
        if k == 0:
            continue
        nn, Dc = category_profile_map(run, hole, cats)
        m = Dc > 0
        if m.sum() > 2:
            ax.plot(nn[m], Dc[m], color=SERIES[k], label=lab, lw=1.1)
    ax.set_yscale("log")
    ax.axvline(0, color=style.TEXT2, lw=0.8, ls="--")
    ax.set_xlabel("расстояние от края отверстия n, мкм  (<0 — отверстие, >0 — золото)")
    ax.set_ylabel("доза, Дж/см³")
    ax.set_title("Профиль дозы поперёк края (центральное сечение, среднее по глубине)\n" + title, fontsize=8)
    ax.legend(fontsize=7, loc="lower left")
    save(fig, outdir / "edge_profile_categories")
    # 4. профили по глубине
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    zmax = run.grids["edge_strip"].z[-1]
    for k, (z0, z1) in enumerate([(0, 2), (6.5, 8.5), (zmax - 2, zmax)]):
        nz, Dz, _ = edge_profile(run, hole, z_range=(z0, z1), rebin_rel_err=0.1)
        m = Dz > 0
        ax.plot(nz[m], Dz[m], color=SERIES[k], marker="o", ms=2, label=f"z = {z0:g}–{z1:g} мкм")
    ax.set_yscale("log")
    ax.axvline(0, color=style.TEXT2, lw=0.8, ls="--")
    ax.set_xlabel("n, мкм")
    ax.set_ylabel("доза, Дж/см³")
    ax.set_title("Профиль края на разной глубине ПММА\n" + title, fontsize=8)
    ax.legend(fontsize=7)
    save(fig, outdir / "edge_profile_depths")
    # 5. глубинная доза
    dd = s["depth_dose"]
    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    ax.plot(dd["z_um"], dd["open_J_cm3"], marker="o", ms=3, color=SERIES[0], label="под отверстием")
    ax.plot(dd["z_um"], dd["shadow_J_cm3"], marker="o", ms=3, color=SERIES[1], label="под золотом (n > 20 мкм)")
    ax.set_yscale("log")
    ax.set_xlabel("глубина в ПММА z, мкм")
    ax.set_ylabel("доза, Дж/см³")
    ax.set_title("Зависимость дозы от глубины\n" + title, fontsize=8)
    ax.legend(fontsize=7)
    save(fig, outdir / "depth_dose")
    # 6. спектры: фотоны на входе в ПММА и энергия первичных фотонов дозы
    e = run.spectra["e_edges_keV"]
    ec = 0.5 * (e[1:] + e[:-1])
    ent = run.spectra["pmma_entry_weight"]
    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    labels = ["без рассеяния", "рассеяны в мембране", "прочие"]
    for k in range(3):
        y = ent[0, k] + ent[1, k] + ent[2, k]
        if y.sum() > 0:
            ax.step(ec, y / y.sum() if k == 0 else y / ent[:, 0].sum(), where="mid", color=SERIES[k], label=labels[k])
    ax.set_yscale("log")
    ax.set_xlim(0, 40)
    ax.set_xlabel("энергия фотона, кэВ")
    ax.set_ylabel("доля (нормировка на нерассеянные)")
    ax.set_title("Спектр фотонов на входе в ПММА\n" + title, fontsize=8)
    ax.legend(fontsize=7)
    save(fig, outdir / "pmma_entry_spectrum")
    ed = run.spectra["edep_by_primary_energy_MeV"]
    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    for k, r in enumerate(["под отверстием", "край", "под золотом"]):
        if ed[k].sum() > 0:
            ax.step(ec, ed[k] / ed[k].sum(), where="mid", color=SERIES[k], label=r)
    ax.set_xlim(0, 40)
    ax.set_xlabel("энергия первичного фотона истории, кэВ")
    ax.set_ylabel("доля энерговыделения")
    ax.set_title("Какие энергии формируют дозу\n" + title, fontsize=8)
    ax.legend(fontsize=7)
    save(fig, outdir / "dose_vs_primary_energy")


def analyze_run(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    run = load_run(run_dir)
    s = summarize(run)
    outdir = run_dir / "analysis"
    outdir.mkdir(exist_ok=True)
    dump_json(s, outdir / "summary.json")
    # профили в CSV
    n, D, S = edge_profile(run, float(run.info["hole_um"]))
    np.savetxt(outdir / "edge_profile_fine.csv", np.c_[n, D, S], delimiter=",",
               header="n_um,dose_J_cm3,sigma_J_cm3 (depth-averaged, folded left/right, native bins)", comments="# ")
    n, D, S = edge_profile(run, float(run.info["hole_um"]), rebin_rel_err=0.05)
    np.savetxt(outdir / "edge_profile.csv", np.c_[n, D, S], delimiter=",",
               header="n_um,dose_J_cm3,sigma_J_cm3 (depth-averaged, folded, adaptively merged to <=5% rel. error)",
               comments="# ")
    plots(run, outdir, s)
    e = s["edge"]
    print(f"[analysis] {run_dir.name}: D_open={e['dose_open_J_cm3']:.3g} Дж/см³, D_shadow={e['dose_shadow_J_cm3']:.3g}, "
          f"ширина 10–90%={e['width_10_90_um']:.3g} мкм, доля рассеяния в мембране (open/shadow)="
          f"{s['membrane_scatter_fraction']['open']:.3g}/{s['membrane_scatter_fraction']['shadow']:.3g}, "
          f"баланс энергии {s['energy_balance_rel_error']:.1e}")
    return s

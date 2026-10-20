"""`liga spectrum`: этапы 1–2 ТЗ — спектр СИ ВЭПП-3, Be-окна, фильтры экспериментов.

Все результаты — в results/spectrum (CSV с размерностями, JSON, PNG/PDF).
Проверки с заранее заданными критериями записываются в checks.json.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from liga_cli.model import EXPERIMENTS, load_experiment
from liga_common.io import dump_json
from material_attenuation.materials import mu_rho_nist, transmission
from plotting.style import SERIES, plt, save
from spectrum_export.tables import SpectrumGrid, build_joint_table, scan_averaged_fluence_rate, static_fluence_rate

from .sr import E_CHARGE, trapz, Source, angular_flux, flux_per_mrad, power_per_mrad_W, psi_rms_mrad

KEV_J = 1e3 * E_CHARGE


def _dose_rate_surface(table, materials, scan_half_mm: float | None, distance_m: float, z_um=(0.0, 1.0)):
    """Аналитическая мощность поглощённой дозы в слое ПММА z0..z1 (Дж/(см³·с)) — без рассеяния."""
    ec = 0.5 * (table.e_edges[1:] + table.e_edges[:-1])
    N = table.energy_spectrum()  # ф/(с·мрад)
    if scan_half_mm:
        flu = N / distance_m / (2 * scan_half_mm)  # ф/(с·мм²)
    else:
        j0 = int(np.searchsorted(table.psi_edges, 0.0, side="right") - 1)
        dpsi = table.psi_edges[j0 + 1] - table.psi_edges[j0]
        flu = table.total[:, j0] / dpsi / distance_m ** 2  # ф/(с·мм²) в медианной плоскости
    pm = materials["PMMA"]
    mu = mu_rho_nist(pm, ec) * pm.density_g_cm3
    muen = mu_rho_nist(pm, ec, "en") * pm.density_g_cm3
    z0, z1 = z_um[0] * 1e-4, z_um[1] * 1e-4
    absorbed = (np.exp(-mu * z0) - np.exp(-mu * z1)) / (z1 - z0) * muen / mu  # 1/см
    return float((flu * 100 * ec * KEV_J * absorbed).sum())


def spectrum_report(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    exp0 = load_experiment("be_200")
    s = exp0.source
    src = exp0.src
    M = exp0.materials
    L = s["distance_m"]
    A = s["scan_half_amplitude_mm"]
    checks = []

    def check(name, value, ref, tol, note=""):
        ok = abs(value - ref) <= tol * abs(ref)
        checks.append({"name": name, "value": value, "reference": ref, "rel_tolerance": tol, "pass": bool(ok),
                       "note": note})
        print(f"  [{'OK ' if ok else 'FAIL'}] {name}: {value:.6g} (ref {ref:.6g}, tol {tol:.1%}) {note}")

    print("== Источник")
    params = {"gamma": src.gamma, "radius_m": src.radius_m, "critical_energy_keV": src.critical_energy_keV,
              "critical_wavelength_A": src.critical_wavelength_A, "opening_angle_1_over_gamma_mrad":
              src.natural_opening_angle_mrad, "power_W_per_mrad_analytic": power_per_mrad_W(src),
              "current_mA": src.current_mA, "electron_energy_GeV": src.electron_energy_GeV, "field_T": src.field_T,
              "distance_m": L}
    dump_json({"source": s, "derived": params}, out / "source_parameters.json")
    check("Критическая энергия, кэВ", src.critical_energy_keV, 5.3, 0.01, "диссертация: 5.3 кэВ")
    check("Критическая длина волны, Å", src.critical_wavelength_A, 2.33, 0.01, "диссертация: 2.33 Å")
    check("Лоренц-фактор", src.gamma, 3914, 0.001, "диссертация: 3914")
    # нормировка мощности: численный интеграл спектра = аналитика (4/9) α γ (I/e) Ec
    E = np.linspace(0.005, 200, 40000)
    F = flux_per_mrad(src, E)
    P_num = float(trapz(F * E * KEV_J, E))
    check("Мощность на мрад (численно = аналитически), Вт/мрад", P_num, power_per_mrad_W(src), 0.002)
    # угловой интеграл формулы Швингера = G1-спектр
    psi = np.linspace(-5, 5, 20001)
    for Ek in (2.0, 5.3, 20.0):
        Aint = float(trapz(angular_flux(src, [Ek], psi)[0], psi))
        check(f"∫dψ (Швингер) = G1-поток при {Ek} кэВ", Aint, float(flux_per_mrad(src, [Ek])[0]), 1e-4)
    # масштабирование с полем: Ec ∝ B
    src3 = Source(src.electron_energy_GeV, 3.0, src.current_mA)
    check("Ec(3 Тл)/Ec(2 Тл)", src3.critical_energy_keV / src.critical_energy_keV, 1.5, 1e-9)
    check("Угол раскрытия ψ_rms(5.3 кэВ) ~ 0.6/γ", psi_rms_mrad(src, src.critical_energy_keV),
          0.6 / src.gamma * 1e3, 0.15, "порядок величины: ψ_rms ≈ 0.6·(1/γ) на E_c")

    # ------------------------------------------------------------------ таблицы
    grid = SpectrumGrid(exp0.spectrum["e_min_keV"], exp0.spectrum["e_max_keV"], exp0.spectrum["e_step_keV"],
                        exp0.spectrum["psi_max_mrad"], exp0.spectrum["psi_step_mrad"])
    raw = build_joint_table(src, grid)
    be = build_joint_table(src, grid, [(M["Be"], float(s["be_windows"]["total_um"]))])
    ec = 0.5 * (raw.e_edges[1:] + raw.e_edges[:-1])
    de = np.diff(raw.e_edges)
    n_raw, n_be = raw.energy_spectrum(), be.energy_spectrum()
    # сходимость по сетке
    fine = build_joint_table(src, SpectrumGrid(grid.e_min_keV, grid.e_max_keV, grid.e_step_keV / 2,
                                               grid.psi_max_mrad, grid.psi_step_mrad / 2),
                             [(M["Be"], float(s["be_windows"]["total_um"]))])
    check("Сходимость сетки: поток после Be (шаг/2)", fine.summary()["photons_per_s_per_mrad"],
          be.summary()["photons_per_s_per_mrad"], 1e-3)
    check("Сходимость сетки: мощность после Be (шаг/2)", fine.summary()["power_W_per_mrad"],
          be.summary()["power_W_per_mrad"], 1e-3)
    # достаточность границ: доля мощности выше 80 кэВ и ниже 1 кэВ после Be
    Ehi = np.linspace(80, 300, 4000)
    P_hi = float(trapz(flux_per_mrad(src, Ehi) * Ehi * KEV_J * transmission(M["Be"], 500, Ehi), Ehi))
    checks.append({"name": "Доля мощности после Be за пределами 80 кэВ", "value": P_hi / be.summary()["power_W_per_mrad"],
                   "criterion": "< 1e-4", "pass": P_hi / be.summary()["power_W_per_mrad"] < 1e-4})
    print(f"  доля мощности > 80 кэВ после Be: {P_hi / be.summary()['power_W_per_mrad']:.2e}")
    # доля потока за |ψ| > ψmax
    wide = build_joint_table(src, SpectrumGrid(grid.e_min_keV, grid.e_max_keV, 0.5, 4.0, 0.05),
                             [(M["Be"], 500.0)])
    narrow_frac = wide.total[:, np.abs(0.5 * (wide.psi_edges[1:] + wide.psi_edges[:-1])) > grid.psi_max_mrad].sum() / \
        wide.total.sum()
    checks.append({"name": f"Доля потока после Be при |ψ| > {grid.psi_max_mrad} мрад", "value": float(narrow_frac),
                   "criterion": "< 1e-4", "pass": bool(narrow_frac < 1e-4)})
    print(f"  доля потока за |ψ|>{grid.psi_max_mrad} мрад: {narrow_frac:.2e}")

    # ------------------------------------------------- сверка с диссертацией
    print("== Сверка с диссертацией Гольденберга")
    be_med = build_joint_table(src, SpectrumGrid(1, 80, 0.1, 0.05, 0.01), [(M["Be"], 500.0)])
    j0 = int(np.searchsorted(be_med.psi_edges, 0.0, side="right") - 1)
    P_med = float((be_med.total[:, j0] / np.diff(be_med.psi_edges)[j0] * ec * KEV_J).sum())  # Вт/мрад²
    P_med_cm2 = P_med / (20.0 * 1e-3 * 1e2) ** 2 * 1e0  # на 20 м: 1 мрад = 2 см → Вт/см²
    check("Плотность мощности в медианной плоскости после 500 мкм Be на 20 м, Вт/см²", P_med_cm2, 3.1, 0.10,
          "табл. 2 диссертации: 3.1 Вт/см² (I=100 мА)")
    t20 = build_joint_table(src, grid, [(M["Be"], 500.0)], psi_limit_mrad=20.0 / 20.0)
    rate_scan = _dose_rate_surface(t20, M, 20.0, 20.0)
    check("Время до 3.5 кДж/см³ (поверхность), сканирование ±20 мм, только Be 500 мкм, мин",
          3500 / rate_scan / 60, 7.75, 0.15, "табл. 3 диссертации: 7′45″")
    rate_static = _dose_rate_surface(t20, M, None, 20.0)
    check("Время до 3.5 кДж/см³, неподвижно в максимуме, мин", 3500 / rate_static / 60, 1.75, 0.25,
          "табл. 3 диссертации: 1′45″")

    # ---------------------------------------------------------- CSV и графики
    hdr = "energy_lo_keV,energy_hi_keV,photons_per_s_per_mrad_raw,photons_per_s_per_mrad_after_Be500," \
          "power_W_per_mrad_raw,power_W_per_mrad_after_Be500"
    np.savetxt(out / "spectrum_flux_power.csv",
               np.c_[raw.e_edges[:-1], raw.e_edges[1:], n_raw, n_be, n_raw * ec * KEV_J, n_be * ec * KEV_J],
               delimiter=",", header=hdr + f"  | E=2 GeV, B=2 T, I={src.current_mA} mA; per bin (bin width 0.1 keV)",
               comments="# ")
    np.savez_compressed(out / "energy_psi_distribution_after_Be.npz", e_edges_keV=be.e_edges,
                        psi_edges_mrad=be.psi_edges, sigma_ph_s_mrad=be.sigma, pi_ph_s_mrad=be.pi)
    fig, ax = plt.subplots(figsize=(6.4, 4))
    ax.plot(ec, n_raw / de, color=SERIES[0], label="без фильтров")
    ax.plot(ec, n_be / de, color=SERIES[1], label="после Be 500 мкм")
    ax.set_yscale("log")
    ax.set_ylim(n_be.max() / de[0] * 1e-6, n_raw.max() / de[0] * 3)
    ax.set_xlabel("энергия фотона, кэВ")
    ax.set_ylabel("фотоны / (с · мрад · кэВ)")
    ax.set_title(f"Спектр СИ ВЭПП-3 (E=2 ГэВ, B=2 Тл, I={src.current_mA:g} мА), интеграл по ψ", fontsize=9)
    ax.legend()
    save(fig, out / "spectrum_flux")
    fig, ax = plt.subplots(figsize=(6.4, 4))
    ax.plot(ec, n_raw * ec * KEV_J / de, color=SERIES[0], label="без фильтров")
    ax.plot(ec, n_be * ec * KEV_J / de, color=SERIES[1], label="после Be 500 мкм")
    ax.set_xlabel("энергия фотона, кэВ")
    ax.set_ylabel("Вт / (мрад · кэВ)")
    ax.set_xlim(0, 40)
    ax.set_title("Спектральная плотность мощности", fontsize=9)
    ax.legend()
    save(fig, out / "spectrum_power")
    fig, ax = plt.subplots(figsize=(6.0, 4.4))
    pc = 0.5 * (be.psi_edges[1:] + be.psi_edges[:-1])
    from matplotlib.colors import LogNorm
    Z = (be.total / de[:, None] / np.diff(be.psi_edges)[None, :]).T
    im = ax.pcolormesh(be.e_edges, be.psi_edges, np.where(Z > 0, Z, np.nan), cmap="Blues",
                       norm=LogNorm(vmin=Z.max() * 1e-4, vmax=Z.max()))
    ax.set_xlim(1, 40)
    ax.set_xlabel("энергия, кэВ")
    ax.set_ylabel("вертикальный угол ψ, мрад")
    ax.set_title("Спектрально-угловое распределение после Be 500 мкм", fontsize=9)
    fig.colorbar(im, ax=ax, label="фотоны/(с·мрад²·кэВ)")
    ax.grid(False)
    save(fig, out / "spectrum_energy_psi")
    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    for k, Ek in enumerate([3.0, 5.3, 10.0, 20.0]):
        p = np.linspace(-1.5, 1.5, 601)
        a = angular_flux(src, [Ek], p, components=True)
        ax.plot(p, (a[0] + a[1])[0] / (a[0] + a[1])[0].max(), color=SERIES[k], label=f"{Ek:g} кэВ")
    ax.set_xlabel("ψ, мрад")
    ax.set_ylabel("отн. интенсивность")
    ax.set_title("Вертикальное угловое распределение (σ+π)", fontsize=9)
    ax.legend()
    save(fig, out / "angular_distribution")

    # ---------------------------------------------------------- Be-окна (этап 2)
    print("== Бериллиевые окна")
    be_rows = []
    for t in (0, 100, 200, 300, 400, 500, 600, 800):
        tt = build_joint_table(src, grid, [(M["Be"], float(t))] if t else [])
        sm = tt.summary()
        be_rows.append({"be_um": t, **sm,
                        "photon_transmission": sm["photons_per_s_per_mrad"] / raw.summary()["photons_per_s_per_mrad"],
                        "power_transmission": sm["power_W_per_mrad"] / raw.summary()["power_W_per_mrad"]})
    dump_json(be_rows, out / "be_windows_thickness_scan.json")
    bands = [(1, 3), (3, 5), (5, 8), (8, 12), (12, 20), (20, 80)]
    band_rows = []
    for lo, hi in bands:
        m = (ec >= lo) & (ec < hi)
        band_rows.append({"band_keV": [lo, hi], "photon_share_raw": float(n_raw[m].sum() / n_raw.sum()),
                          "photon_share_after_Be": float(n_be[m].sum() / n_be.sum()),
                          "power_share_after_Be": float((n_be * ec)[m].sum() / (n_be * ec).sum())})
    dump_json(band_rows, out / "be_windows_energy_bands.json")
    for r in be_rows:
        print(f"  Be {r['be_um']:4d} мкм: T_photons={r['photon_transmission']:.3f}, T_power={r['power_transmission']:.3f},"
              f" <E>={r['mean_energy_keV']:.2f} кэВ")

    # ------------------------------------------------- спектры экспериментов
    print("== Спектры после фильтров (аналитически, нерассеянная компонента)")
    exp_rows = []
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    for k, eid in enumerate(EXPERIMENTS):
        ex = load_experiment(eid)
        g = ex.geo
        filt = [(M["Be"], 500.0), (M["Al"], float(g["al_filter_um"]))]
        mem = g["membrane"]
        filt.append((ex.materials[mem["material"]], float(mem["thickness_um"])))
        filt += [(M["Ti"], float(g["mask"]["support"]["thickness_um"])), (M["Kapton"], float(g["kapton_um"]))]
        t = build_joint_table(src, grid, filt, psi_limit_mrad=A / L)
        sm = t.summary()
        rate = scan_averaged_fluence_rate(t, L, A)
        Q = float(ex.exp["exposure_mA_min"])
        d_top = _dose_rate_surface(t, M, A, L, (0, 1)) / src.current_mA * Q * 60
        d_bot = _dose_rate_surface(t, M, A, L, (14, 15)) / src.current_mA * Q * 60
        exp_rows.append({"experiment": eid, "filters": [(m.name, d) for m, d in filt], **sm,
                         "photon_fluence_rate_ph_s_mm2_at_100mA": rate,
                         "exposure_mA_min": Q, "dose_pmma_top_J_cm3_open": d_top, "dose_pmma_bottom_J_cm3_open": d_bot,
                         "note": "аналитика без рассеяния и вторичного излучения; открытая область (под отверстием)"})
        print(f"  {eid:18s}: <E>={sm['mean_energy_keV']:.1f} кэВ, D_top={d_top:.0f} Дж/см³, D_bottom={d_bot:.0f} Дж/см³")
        n = t.energy_spectrum()
        ax.plot(ec, n / de, color=SERIES[k], label=eid)
    ax.set_yscale("log")
    ax.set_xlabel("энергия фотона, кэВ")
    ax.set_ylabel("фотоны / (с · мрад · кэВ) у ПММА")
    ax.set_xlim(0, 60)
    ax.set_title("Спектр на входе в ПММА под отверстием (нерассеянная компонента)", fontsize=9)
    ax.legend(fontsize=7)
    save(fig, out / "spectra_experiments")
    dump_json(exp_rows, out / "experiments_spectra.json")
    dump_json(checks, out / "checks.json")
    n_fail = sum(not c["pass"] for c in checks)
    print(f"== Проверок: {len(checks)}, не пройдено: {n_fail}")
    return {"checks": checks, "experiments": exp_rows}

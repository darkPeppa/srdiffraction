"""`liga report`: сводные таблицы и графики по всем выполненным расчётам."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from liga_common.io import dump_json
from plotting.style import SERIES, plt, save

from .run_analysis import find_runs

ORDER = ["be_200", "carbon_475", "sapphire_contact", "sapphire_280mm", "titanium_model"]
TITLES = {"be_200": "Be 200 мкм (контакт)", "carbon_475": "Стеклоуглерод 475 мкм (контакт)",
          "sapphire_contact": "Al₂O₃ 525 мкм (контакт)", "sapphire_280mm": "Al₂O₃ 525 мкм (280 мм)",
          "titanium_model": "Ti 2.3 мкм (только расчёт)"}


def _fmt(x, f="{:.3g}"):
    return f.format(x) if isinstance(x, (int, float)) and x == x else "—"


def build_report(results: Path, out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for rd in find_runs(results / "runs"):
        s = rd / "analysis" / "summary.json"
        if not s.exists():
            continue
        d = json.loads(s.read_text(encoding="utf-8"))
        d["run_dir"] = str(rd.relative_to(results))
        rows.append(d)
    rows.sort(key=lambda d: (ORDER.index(d["experiment"]) if d["experiment"] in ORDER else 9, d["hole_um"]))
    dump_json(rows, out / "all_runs_summary.json")
    L = ["# Сводный отчёт по расчётам", "",
         "Доза — Дж/см³ за экспозицию эксперимента (мА·мин из техзадания; для Ti — принятая общая нормировка). "
         "«Открыто» — под отверстием вдали от края, «тень» — под золотом дальше 20 мкм от края. "
         "Доли рассеяния — доля энерговыделения историй с рассеянием (перекрывающийся признак).", "",
         "| Конфигурация | Отверстие, мкм | Профиль | N | D открыто | D тень | Контраст | Ширина 10–90 %, мкм | "
         "Доля: рассеяние в мембране (откр./тень) | Доля: любое рассеяние вне ПММА (откр./тень) | ⟨E⟩ первичных дозы, кэВ |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for d in rows:
        e = d["edge"]
        mf, af = d["membrane_scatter_fraction"], d["any_scatter_fraction"]
        L.append(f"| {TITLES.get(d['experiment'], d['experiment'])} | {d['hole_um']:g} | {d['profile']} | "
                 f"{d['n_histories']:.1e} | {_fmt(e['dose_open_J_cm3'])} | {_fmt(e['dose_shadow_J_cm3'])} | "
                 f"{_fmt(e['contrast_open_to_shadow'])} | {_fmt(e['width_10_90_um'])} | "
                 f"{_fmt(mf['open'], '{:.2%}')} / {_fmt(mf['shadow'], '{:.2%}')} | "
                 f"{_fmt(af['open'], '{:.2%}')} / {_fmt(af['shadow'], '{:.2%}')} | "
                 f"{_fmt(d['mean_primary_energy_of_dose_keV']['open'])} |")
    L += ["", "## Разложение дозы по непересекающимся категориям (регион «тень»)", "",
          "| Конфигурация | Отверстие | " + " | ".join(
              ["прямое", "мембрана: рэлей", "мембрана: комптон", "Al", "Be-окна", "Ti-основа", "прочее рассеяние",
               "внутри ПММА", "вторичное извне"]) + " |", "|---" * 11 + "|"]
    for d in rows:
        cf = d["category_fractions"]["shadow"]
        vals = [cf.get(k) for k in ["direct", "membrane_rayleigh_only", "membrane_compton", "al_filter_scatter",
                                    "be_window_scatter", "mask_support_scatter", "other_scatter", "pmma_self_scatter",
                                    "external_secondary"]]
        L.append(f"| {TITLES.get(d['experiment'], d['experiment'])} | {d['hole_um']:g} | " +
                 " | ".join(_fmt(v, "{:.2%}") for v in vals) + " |")
    L += ["", "Статистические погрешности и графики — в каталоге каждого прогона (analysis/). "
          "Это демонстрационная статистика профиля quick, если не указано иное."]
    p = out / "summary.md"
    p.write_text("\n".join(L) + "\n", encoding="utf-8")
    # график: доля рассеяния в мембране по материалам
    if rows:
        fig, ax = plt.subplots(figsize=(7, 4))
        exps = [e for e in ORDER if any(d["experiment"] == e for d in rows)]
        for k, e in enumerate(exps):
            rr = [d for d in rows if d["experiment"] == e]
            ax.plot([d["hole_um"] for d in rr], [100 * d["membrane_scatter_fraction"]["shadow"] for d in rr],
                    marker="o", color=SERIES[k], label=f"{TITLES[e]} — тень")
            ax.plot([d["hole_um"] for d in rr], [100 * d["membrane_scatter_fraction"]["open"] for d in rr],
                    marker="s", ls="--", color=SERIES[k], label=f"{TITLES[e]} — открыто")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("размер отверстия, мкм")
        ax.set_ylabel("доля дозы от историй с рассеянием в мембране, %")
        ax.set_title("Вклад рассеяния в исследуемой мембране", fontsize=9)
        ax.legend(fontsize=6)
        save(fig, out / "membrane_scatter_by_material")
    print(f"  сводка: {p} ({len(rows)} прогонов)")
    return p

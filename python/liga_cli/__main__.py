"""Единый CLI проекта (вызывается из контейнера: `./run.sh <команда> ...`)."""
from __future__ import annotations

import argparse
import sys
import time

from . import commands


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="liga", description="LIGA / Geant4: рассеяние СИ в мембранах масок (ВЭПП-3)",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=commands.EPILOG)
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("help", help="справка")
    sub.add_parser("info", help="версии окружения, проверка установки")

    s = sub.add_parser("spectrum", help="этапы 1–2: спектр СИ, Be-окна, фильтры (Python, быстро)")
    s.add_argument("--out", default="results/spectrum")

    s = sub.add_parser("materials", help="материалы: таблица Geant4 vs NIST XCOM")
    s.add_argument("--physics", default="livermore")
    s.add_argument("--out", default="results/materials")

    s = sub.add_parser("simulate", help="моделирование эксперимента (этап 1 + этап 2) и анализ")
    s.add_argument("experiment", help="be_200 | carbon_475 | sapphire_contact | sapphire_280mm | titanium_model | all")
    s.add_argument("--hole", type=float, action="append", help="размер отверстия, мкм (можно несколько); по умолчанию все")
    s.add_argument("--profile", default="quick", choices=["quick", "standard", "production"])
    s.add_argument("--upstream", default="stage1", choices=["stage1", "analytic"])
    s.add_argument("--events", type=int, help="число историй этапа 2")
    s.add_argument("--stage1-events", type=int)
    s.add_argument("--window-extra-mm", type=float)
    s.add_argument("--physics", help="livermore | livermore_polarized | penelope | option4 | standard")
    s.add_argument("--no-membrane", action="store_true", help="контроль: без исследуемой мембраны")
    s.add_argument("--medium", help="среда: He_chamber | Vacuum | Air")
    s.add_argument("--seed", type=int)
    s.add_argument("--threads", type=int, default=0)
    s.add_argument("--tag", default="", help="суффикс каталога результатов")
    s.add_argument("--out", default="results/runs")
    s.add_argument("--no-analysis", action="store_true")

    s = sub.add_parser("analyze", help="анализ готовых прогонов (карты дозы, профили, разложение)")
    s.add_argument("runs", nargs="*", help="каталоги прогонов (по умолчанию все в results/runs)")

    s = sub.add_parser("compare", help="уровень A: сравнение с аппроксимациями профилей из техзаданий")
    s.add_argument("--runs", default="results/runs")
    s.add_argument("--out", default="results/comparison")

    s = sub.add_parser("validate", help="проверки физики и численные тесты (ТЗ п. 11)")
    s.add_argument("--quick", action="store_true", help="сокращённая статистика (~5–10 мин)")
    s.add_argument("--only", action="append", help="запустить только указанные проверки")
    s.add_argument("--out", default="results/validation")

    s = sub.add_parser("test", help="быстрые автоматические тесты: C++ unit + pytest (~2–5 мин)")
    s.add_argument("--fast", action="store_true", help="только тесты без Geant4-транспорта")

    s = sub.add_parser("report", help="сводный отчёт по всем результатам")
    s.add_argument("--out", default="results/report")

    s = sub.add_parser("all", help="полный конвейер: test → spectrum → materials → validate → simulate → compare → report")
    s.add_argument("--profile", default="quick", choices=["quick", "standard", "production"])

    # --- интерферометрия (дополнение к этапу 8)
    s = sub.add_parser("inventory-interferograms", help="реестр архива интерферограмм, контактные листы")
    s.add_argument("--archive", default="data/experimental_profiles/interferograms")
    s.add_argument("--out", default="results/interferometry")
    s = sub.add_parser("annotate-roi", help="HTML-инструмент ручной разметки ROI (сохраняет JSON)")
    s.add_argument("--archive", default="data/experimental_profiles/interferograms")
    s.add_argument("--out", default="results/interferometry/roi_editor")
    s.add_argument("--file", action="append", help="только эти файлы (относительные пути)")
    s = sub.add_parser("reconstruct-fringes", help="восстановление фазы/рельефа (2 независимых метода)")
    s.add_argument("--archive", default="data/experimental_profiles/interferograms")
    s.add_argument("--roi", default="config/interferometry_roi")
    s.add_argument("--out", default="results/interferometry")
    s.add_argument("--file", action="append")
    s = sub.add_parser("validate-supervisor-profiles", help="проверка аппроксимаций руководителя (формулы из DOCX)")
    s.add_argument("--out", default="results/interferometry")
    s = sub.add_parser("assign-mask-features", help="гипотезы атрибуции кадров ↔ отверстия")
    s.add_argument("--out", default="results/interferometry")
    s = sub.add_parser("compare-geant4", help="Geant4 + модель проявления ↔ восстановленные профили")
    s.add_argument("--runs", default="results/runs")
    s.add_argument("--out", default="results/interferometry")
    s = sub.add_parser("build-interferometry-report", help="отчёт по интерферометрии")
    s.add_argument("--out", default="results/interferometry")
    return p


def main(argv=None) -> int:
    p = build_parser()
    a = p.parse_args(argv)
    if not a.cmd or a.cmd == "help":
        p.print_help()
        return 0
    t0 = time.time()
    fn = getattr(commands, "cmd_" + a.cmd.replace("-", "_"))
    rc = fn(a) or 0
    print(f"[liga] {a.cmd}: done in {time.time() - t0:.1f} s (rc={rc})")
    return rc


if __name__ == "__main__":
    sys.exit(main())

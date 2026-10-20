"""Реализация команд CLI. Тяжёлые модули импортируются лениво."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from liga_common.paths import LIGA_UNIT_TESTS, REPO, RESULTS, ensure

EPILOG = """
Примеры (из корня репозитория, на хосте):
  ./run.sh test                          быстрые тесты (~2–5 мин)
  ./run.sh spectrum                      спектр СИ ВЭПП-3, окна, фильтры
  ./run.sh simulate be_200 --hole 200    один эксперимент/отверстие, профиль quick
  ./run.sh simulate all --profile quick  все конфигурации (демо-статистика)
  ./run.sh validate --quick              физические проверки
  ./run.sh compare                       сравнение с профилями из техзаданий
  ./run.sh all                           весь конвейер
Подробно: README.md, docs/.
"""


# Пути результатов, созданных текущей командой (для --persist)
TOUCHED: list[Path] = []


def _touch(p: Path) -> Path:
    TOUCHED.append(Path(p))
    return Path(p)


def _resolve(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else REPO / q


# ------------------------------------------------------------------------- info
def cmd_info(a) -> int:
    from liga_common.io import environment_info
    info = environment_info()
    for k, v in info.items():
        print(f"{k:12s} {v}")
    print(f"{'repo':12s} {REPO}")
    print(f"{'threads':12s} {os.environ.get('LIGA_THREADS', '0')} (0 = все ядра: {os.cpu_count()})")
    return 0


# --------------------------------------------------------------------- spectrum
def cmd_spectrum(a) -> int:
    from synchrotron_spectrum.report import spectrum_report
    spectrum_report(_touch(_resolve(a.out)))
    return 0


def cmd_materials(a) -> int:
    from material_attenuation.report import materials_report
    materials_report(_touch(_resolve(a.out)), a.physics)
    return 0


# --------------------------------------------------------------------- simulate
def cmd_simulate(a) -> int:
    from .model import EXPERIMENTS, load_experiment
    from .runner import RunOptions, simulate

    exps = EXPERIMENTS if a.experiment == "all" else [a.experiment]
    overrides = {}
    if a.physics:
        overrides["physics"] = {"em": a.physics}
    if a.no_membrane:
        overrides["no_membrane"] = True
    if a.medium:
        overrides["medium"] = a.medium
    opts = RunOptions(profile=a.profile, upstream=a.upstream, stage1_events=a.stage1_events, stage2_events=a.events,
                      window_extra_mm=a.window_extra_mm, threads=a.threads, seed=a.seed, tag=a.tag)
    out = _resolve(a.out)
    done = []
    for e in exps:
        exp = load_experiment(e, overrides)
        holes = a.hole or exp.holes
        for h in holes:
            tag = f"{e}/hole_{h:g}um_{a.profile}" + (f"_{a.tag}" if a.tag else "")
            if a.no_membrane:
                tag += "_nomembrane"
            if a.upstream == "analytic":
                tag += "_analytic"
            if a.physics:
                tag += f"_{a.physics}"
            run_dir = out / tag
            print(f"\n=== {e}: отверстие {h:g} мкм → {run_dir}")
            simulate(exp, h, opts, run_dir)
            done.append(_touch(run_dir))
            if not a.no_analysis:
                from analysis.run_analysis import analyze_run
                analyze_run(run_dir)
    for d in done:  # кэши этапа 1 (их конфигурации и логи — часть следа прогона; *.bin не сохраняются)
        info = d / "run_info.json"
        if info.exists():
            st1 = json.loads(info.read_text(encoding="utf-8")).get("stage1", {}).get("dir")
            if st1:
                _touch(Path(st1))
    print("\nГотово:", *[str(d) for d in done], sep="\n  ")
    return 0


def cmd_analyze(a) -> int:
    from analysis.run_analysis import analyze_run, find_runs
    runs = [Path(r) for r in a.runs] if a.runs else find_runs(RESULTS / "runs")
    for r in runs:
        analyze_run(_touch(_resolve(str(r))))
    return 0


def cmd_compare(a) -> int:
    from comparison.level_a import compare_all
    compare_all(_resolve(a.runs), _touch(_resolve(a.out)))
    return 0


def cmd_validate(a) -> int:
    from liga_cli.validation import run_validation
    return run_validation(_touch(_resolve(a.out)), quick=a.quick, only=a.only)


def cmd_report(a) -> int:
    from analysis.summary import build_report
    build_report(RESULTS, _touch(_resolve(a.out)))
    return 0


# ------------------------------------------------------------------------- test
def cmd_test(a) -> int:
    rc = 0
    print("== C++ unit tests")
    rc |= subprocess.call([LIGA_UNIT_TESTS])
    print("== pytest")
    args = [sys.executable, "-m", "pytest", "-q", str(REPO / "tests"), "-p", "no:cacheprovider"]
    if a.fast:
        args += ["-m", "not geant4"]
    rc |= subprocess.call(args, cwd=str(REPO))
    print("ИТОГ:", "все тесты пройдены" if rc == 0 else "есть ошибки")
    return rc


def cmd_all(a) -> int:
    from types import SimpleNamespace as NS
    steps = [
        ("test", lambda: cmd_test(NS(fast=False))),
        ("spectrum", lambda: cmd_spectrum(NS(out="results/spectrum"))),
        ("materials", lambda: cmd_materials(NS(out="results/materials", physics="livermore"))),
        ("validate", lambda: cmd_validate(NS(out="results/validation", quick=a.profile == "quick", only=None))),
        ("simulate", lambda: cmd_simulate(NS(experiment="all", hole=None, profile=a.profile, upstream="stage1",
                                             events=None, stage1_events=None, window_extra_mm=None, physics=None,
                                             no_membrane=False, medium=None, seed=None, threads=0, tag="",
                                             out="results/runs", no_analysis=False))),
        ("compare", lambda: cmd_compare(NS(runs="results/runs", out="results/comparison"))),
        ("interferometry", lambda: _interferometry_all()),
        ("report", lambda: cmd_report(NS(out="results/report"))),
    ]
    failed = []
    for name, fn in steps:
        print(f"\n######## {name}")
        try:
            if fn():
                failed.append(name)
        except Exception as e:  # noqa: BLE001 — продолжаем конвейер, ошибку сообщаем в итоге
            print(f"[liga] step {name} failed: {e}")
            failed.append(name)
    TOUCHED[:] = [RESULTS]
    print("\nИТОГ конвейера:", "успешно" if not failed else f"ошибки на шагах: {failed}")
    return 1 if failed else 0


# ---------------------------------------------------------------- интерферометрия
def _interferometry_all() -> int:
    from types import SimpleNamespace as NS
    out = "results/interferometry"
    cmd_inventory_interferograms(NS(archive="data/experimental_profiles/interferograms", out=out))
    cmd_validate_supervisor_profiles(NS(out=out))
    cmd_reconstruct_fringes(NS(archive="data/experimental_profiles/interferograms", roi="config/interferometry_roi",
                               out=out, file=None))
    cmd_assign_mask_features(NS(out=out))
    cmd_build_interferometry_report(NS(out=out))
    return 0


def cmd_inventory_interferograms(a) -> int:
    from experimental_interferometry.archive_inventory import run_inventory
    run_inventory(_resolve(a.archive), _touch(ensure(_resolve(a.out))))
    return 0


def cmd_annotate_roi(a) -> int:
    from experimental_interferometry.roi_editor import build_editor
    build_editor(_resolve(a.archive), _touch(ensure(_resolve(a.out))), a.file)
    return 0


def cmd_reconstruct_fringes(a) -> int:
    from experimental_interferometry.reports import reconstruct_all
    reconstruct_all(_resolve(a.archive), _resolve(a.roi), _touch(ensure(_resolve(a.out))), a.file)
    return 0


def cmd_validate_supervisor_profiles(a) -> int:
    from experimental_interferometry.legacy_fit_compare import validate_supervisor_profiles
    validate_supervisor_profiles(_touch(ensure(_resolve(a.out))))
    return 0


def cmd_assign_mask_features(a) -> int:
    from experimental_interferometry.attribution import assign_features
    assign_features(_touch(ensure(_resolve(a.out))))
    return 0


def cmd_compare_geant4(a) -> int:
    from experimental_interferometry.geant4_compare import compare_geant4
    compare_geant4(_resolve(a.runs), _touch(ensure(_resolve(a.out))))
    return 0


def cmd_build_interferometry_report(a) -> int:
    from experimental_interferometry.reports import build_report
    build_report(_touch(ensure(_resolve(a.out))))
    return 0

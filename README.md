# LIGA / Geant4: рассеяние СИ ВЭПП-3 в мембранах рентгеношаблонов

Geant4 (C++) + Python. Считает долю дозы в ПММА 15 мкм от историй рассеяния в мембранах
(Be, стеклоуглерод, Al₂O₃, Ti) и её распределение у краёв окон шаблона, а также обрабатывает
архивные интерферограммы. **Всё собирается и запускается в Docker**: на хосте нужен только Docker
Desktop. Работает на Windows, macOS (Intel и Apple Silicon) и Linux.

## Быстрый старт

1. Установите и запустите Docker Desktop. В настройках (Resources) дайте ему все ядра и не меньше 6 ГБ памяти.
2. В корне репозитория:

| macOS / Linux | Windows |
|---|---|
| `./run.sh build` | `run.cmd build` (или `.\run.ps1 build`) |
| `./run.sh test` | `run.cmd test` |
| `./run.sh all` | `run.cmd all` |

**Первая сборка занимает 25–40 минут:** компилируется Geant4 11.3.2 и скачивается около 350 МБ данных
с CERN (сервер отдаёт примерно 0,4 МБ/с). Следующие сборки идут из кэша и занимают секунды или 1–2 минуты.

## Команды и время (8 ядер Apple M2)

| Команда | Что делает | Время |
|---|---|---|
| `test` | модульные тесты C++ и pytest (50 тестов) | ~0,5 мин |
| `spectrum` | спектр СИ, Be-окна, фильтры, сверка с диссертацией | ~0,5 мин |
| `materials` | коэффициенты Geant4 против NIST | ~0,1 мин |
| `validate --quick` | все численные проверки ТЗ п. 11 | ~5 мин |
| `simulate be_200 --hole 200` | один эксперимент и отверстие, профиль quick | ~1,5 мин |
| `simulate all` | 5 конфигураций, 22 отверстия, quick | **~35 мин** |
| `simulate all --profile standard` | рабочая статистика | **~4–6 ч** |
| `compare`, `report` | сравнение уровня A, сводные таблицы | <1 мин |
| интерферометрия (`inventory-interferograms`, `reconstruct-fringes`, …) | 106 снимков | ~10 мин |
| `all` | весь конвейер (quick) | **~1 ч** |

Число потоков задаётся так: `LIGA_THREADS=4 ./run.sh ...` (по умолчанию используются все ядра). Справка по всем командам — `./run.sh help`.
Результаты пишутся в `results/`: HDF5, PNG/PDF, JSON, Markdown-отчёты.

## Структура

```
run.sh / run.ps1 / run.cmd   единая точка входа (Docker)
docker/                      Dockerfile (Ubuntu 24.04 + Geant4 11.3.2 + Python), entrypoint
config/                      source, materials, simulation, 5 экспериментов, interferometry, validation
geant4/                      приложение liga_sim (C++), модульные тесты
python/                      synchrotron_spectrum, material_attenuation, spectrum_export, liga_cli,
                             analysis, comparison, plotting, experimental_interferometry
tests/                       pytest
data/                        source_documents (ТЗ, схемы), experimental_profiles (интерферограммы,
                             формулы профилей), reference_data (NIST)
docs/                        разбор физики, параметры и расхождения, геометрия, нормировка,
                             сравнение и подводные камни, интерферометрия, вопросы, разбор старого кода
legacy/                      прежний код Geant4 и модели G4beamline (без изменений)
```

Начните с `docs/physics_model.md`, затем `docs/comparison.md` (подводные камни) и `docs/questions.md`.

## Советы для Windows

* Если PowerShell запрещает скрипты, используйте `run.cmd`.
* Лучшая производительность: клонируйте репозиторий внутрь WSL2 и запускайте `./run.sh`.
* Окончания строк нормализует `.gitattributes`. Скрипты, работающие внутри контейнера, дополнительно очищаются от CRLF при сборке.

#!/usr/bin/env bash
# =============================================================================
#  Единая точка входа (Linux / macOS). Всё выполняется внутри Docker:
#    ./run.sh build            — собрать образ (первый раз ~25–40 мин: Geant4 + данные)
#    ./run.sh test             — быстрые тесты
#    ./run.sh <команда> ...    — любая команда CLI `liga` (./run.sh help)
#    ./run.sh shell            — интерактивная оболочка в контейнере
#  Число потоков: LIGA_THREADS=4 ./run.sh simulate ...   (0/пусто — все ядра)
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"
command -v docker >/dev/null || { echo "Docker не найден. Установите Docker Desktop: https://docs.docker.com/get-docker/"; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker не запущен. Запустите Docker Desktop и повторите."; exit 1; }
if [[ "${1:-}" == "build" ]]; then
  shift
  exec docker compose build "$@"
fi
# Сборка/обновление образа (кэшируется: если исходники не менялись, занимает секунды)
docker compose build --quiet
TTY=""; [[ -t 0 && -t 1 ]] && TTY="-it"
if [[ "${1:-}" == "shell" ]]; then
  exec docker compose run --rm $TTY liga bash
fi
exec docker compose run --rm $TTY liga "${@:-help}"

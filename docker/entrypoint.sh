#!/usr/bin/env bash
# Точка входа контейнера: окружение Geant4 + единый CLI `liga`.
set -euo pipefail
# shellcheck disable=SC1091
source /opt/geant4/bin/geant4.sh >/dev/null 2>&1 || true
# Если репозиторий смонтирован в /work — используем его Python-код (актуальная версия),
# иначе — копию, встроенную в образ.
if [[ -d /work/python/liga_cli ]]; then
  export PYTHONPATH=/work/python
else
  export PYTHONPATH=/opt/liga/python
fi
export LIGA_SIM=${LIGA_SIM:-/opt/liga/bin/liga_sim}
export LIGA_UNIT_TESTS=${LIGA_UNIT_TESTS:-/opt/liga/bin/liga_unit_tests}
case "${1:-help}" in
  bash|sh|shell) shift || true; exec bash "$@" ;;
  *) exec python3 -m liga_cli "$@" ;;
esac

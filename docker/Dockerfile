# =============================================================================
#  LIGA / Geant4 research package — единый образ для сборки и запуска.
#
#  Стадии:
#    deps    — Ubuntu 24.04 + компилятор, CMake, HDF5, Python-стек (из apt,
#              без обращения к PyPI — воспроизводимо и одинаково на amd64/arm64)
#    geant4  — Geant4 из исходников (только нужные данные: G4EMLOW, G4ENSDFSTATE)
#    app     — приложение liga_sim (C++) + Python-пакеты + CLI `liga`
#
#  Образ мультиархитектурный: собирается нативно и на x86_64 (Windows/Linux/
#  Intel Mac), и на arm64 (Apple Silicon) — эмуляции нет.
# =============================================================================

ARG UBUNTU_VERSION=24.04

# -----------------------------------------------------------------------------
FROM ubuntu:${UBUNTU_VERSION} AS deps
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=UTC
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake ninja-build curl ca-certificates \
        libexpat1-dev zlib1g-dev libhdf5-dev nlohmann-json3-dev \
        python3 python3-numpy python3-scipy python3-pandas python3-matplotlib \
        python3-h5py python3-yaml python3-pytest python3-pil python3-skimage \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
FROM deps AS geant4
ARG GEANT4_VERSION=11.3.2
# Число параллельных задач компиляции. 0 = автоматически по CPU и памяти
# (≈1.5 ГБ на задачу, чтобы сборка не упала по OOM при 8 ГБ у Docker Desktop).
ARG BUILD_JOBS=0
RUN set -eux; \
    mkdir -p /opt/src && cd /opt/src; \
    curl -fsSL --retry 5 -o geant4.tar.gz \
        "https://github.com/Geant4/geant4/archive/refs/tags/v${GEANT4_VERSION}.tar.gz"; \
    tar xzf geant4.tar.gz && rm geant4.tar.gz; \
    jobs="${BUILD_JOBS}"; \
    if [ "$jobs" = "0" ]; then \
        mem_kb=$(awk '/MemTotal/{print $2}' /proc/meminfo); \
        by_mem=$(( mem_kb / 1500000 )); [ "$by_mem" -lt 1 ] && by_mem=1; \
        jobs=$(nproc); [ "$by_mem" -lt "$jobs" ] && jobs=$by_mem; \
    fi; \
    echo "Geant4 build jobs: $jobs"; \
    cmake -S geant4-${GEANT4_VERSION} -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/opt/geant4 \
        -DGEANT4_BUILD_MULTITHREADED=ON \
        -DGEANT4_INSTALL_DATA=OFF \
        -DGEANT4_INSTALL_DATADIR=/opt/geant4/data \
        -DGEANT4_USE_SYSTEM_EXPAT=ON \
        -DGEANT4_USE_SYSTEM_ZLIB=ON \
        -DGEANT4_USE_GDML=OFF \
        -DGEANT4_USE_QT=OFF \
        -DGEANT4_USE_OPENGL_X11=OFF \
        -DGEANT4_BUILD_EXAMPLES=OFF; \
    cmake --build build -j "$jobs"; \
    cmake --install build; \
    rm -rf /opt/src
# Только используемые наборы данных (ЭМ-физика низких энергий + состояния ядер,
# которые Geant4 читает при инициализации таблицы ионов). Список и URL берём
# у самой установленной версии Geant4, поэтому версии наборов всегда совместимы.
RUN set -eux; \
    mkdir -p /opt/geant4/data; cd /opt/geant4/data; \
    /opt/geant4/bin/geant4-config --datasets | tee /opt/geant4/datasets.txt; \
    for name in G4EMLOW G4ENSDFSTATE; do \
      line=$(awk -v n="$name" '$1==n' /opt/geant4/datasets.txt); \
      url=$(echo "$line" | tr -s ' \t' '\n\n' | grep -E '^https?://' | head -1 || true); \
      if [ -z "$url" ]; then \
        dir=$(echo "$line" | tr -s ' \t' '\n\n' | grep '/' | head -1); \
        ver=$(basename "$dir" | sed "s/^${name}//"); \
        url="https://cern.ch/geant4-data/datasets/${name}.${ver}.tar.gz"; \
      fi; \
      echo "download $name from $url"; \
      curl -fsSL --retry 5 "$url" | tar xz; \
    done; \
    ls -la /opt/geant4/data
# PhotonEvaporation: читается при инициализации любого физического списка
# (G4NuclearLevelData через G4EmBuilder). Отдельный слой — чтобы не перекачивать G4EMLOW.
RUN set -eux; cd /opt/geant4/data; \
    for name in PhotonEvaporation; do \
      line=$(awk -v n="$name" '$1==n' /opt/geant4/datasets.txt); \
      dir=$(echo "$line" | tr -s ' \t' '\n\n' | grep '/' | head -1); \
      ver=$(basename "$dir" | sed "s/^${name}//"); \
      url="https://cern.ch/geant4-data/datasets/G4${name}.${ver}.tar.gz"; \
      echo "download $name from $url"; \
      curl -fsSL --retry 5 "$url" | tar xz; \
    done; \
    ls -la /opt/geant4/data

# -----------------------------------------------------------------------------
FROM geant4 AS app
ENV GEANT4_DIR=/opt/geant4 \
    LIGA_HOME=/opt/liga \
    PYTHONPATH=/opt/liga/python \
    PYTHONDONTWRITEBYTECODE=1 \
    MPLBACKEND=Agg \
    LD_LIBRARY_PATH=/opt/geant4/lib \
    PATH=/opt/liga/bin:/opt/geant4/bin:${PATH}

# C++ приложение: собирается внутри образа, исходники копируются из репозитория.
COPY geant4/ /opt/liga/src/geant4/
RUN set -eux; \
    cmake -S /opt/liga/src/geant4 -B /opt/liga/build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/liga \
        -DCMAKE_PREFIX_PATH=/opt/geant4; \
    cmake --build /opt/liga/build -j "$(nproc)"; \
    cmake --install /opt/liga/build

# Python-пакеты и CLI (копия на случай запуска без монтирования репозитория).
COPY python/ /opt/liga/python/
COPY docker/entrypoint.sh /opt/liga/bin/liga
# Защита от CRLF, если репозиторий был склонирован на Windows без .gitattributes.
RUN sed -i 's/\r$//' /opt/liga/bin/liga && chmod +x /opt/liga/bin/liga

WORKDIR /work
ENTRYPOINT ["/opt/liga/bin/liga"]
CMD ["help"]

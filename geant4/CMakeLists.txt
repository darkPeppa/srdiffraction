# =============================================================================
#  liga_sim — Geant4-приложение (C++17). Собирается внутри Docker-образа.
# =============================================================================
cmake_minimum_required(VERSION 3.16)
project(liga_sim CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

find_package(Geant4 REQUIRED)          # без UI/визуализации: пакетный режим
find_package(HDF5 REQUIRED COMPONENTS C)
find_package(nlohmann_json 3.2 REQUIRED)

file(GLOB LIGA_SOURCES ${PROJECT_SOURCE_DIR}/src/*.cc)
add_library(liga_core STATIC ${LIGA_SOURCES})
target_include_directories(liga_core PUBLIC ${PROJECT_SOURCE_DIR}/include ${HDF5_INCLUDE_DIRS})
target_link_libraries(liga_core PUBLIC ${Geant4_LIBRARIES} ${HDF5_C_LIBRARIES} nlohmann_json::nlohmann_json)
target_compile_definitions(liga_core PUBLIC ${Geant4_DEFINITIONS})
target_compile_options(liga_core PRIVATE -Wall -Wextra -Wno-unused-parameter)

add_executable(liga_sim app/liga_sim.cc)
target_link_libraries(liga_sim PRIVATE liga_core)

# Модульные тесты C++ (без транспорта частиц): классификация меток, сетка, таблица источника.
add_executable(liga_unit_tests tests/unit_tests.cc)
target_link_libraries(liga_unit_tests PRIVATE liga_core)
enable_testing()
add_test(NAME unit_tests COMMAND liga_unit_tests)

install(TARGETS liga_sim liga_unit_tests DESTINATION bin)

# Настройка проекта
set(name srdiffraction)
cmake_minimum_required(VERSION 3.16...3.21)
project(${name})

# Поиск Geant4 библиотек. Активация доступных UI и визуализационный драйверов
# Если в задаче нет визуализации, её можно не подгружать, оставив в коде ниже только find_package(Geant4 REQUIRED)
option(WITH_GEANT4_UIVIS "Build example with Geant4 UI and Vis drivers" ON)
if(WITH_GEANT4_UIVIS)
  find_package(Geant4 REQUIRED ui_all vis_all)
else()
  find_package(Geant4 REQUIRED)
endif()

# Настройка путей к заголовочным файлам Geant4 и параметров компиляции
include(${Geant4_USE_FILE})

# Поиск sources и header файлов для проекта
include_directories(${PROJECT_SOURCE_DIR}/include 
                    ${Geant4_INCLUDE_DIR})
file(GLOB sources ${PROJECT_SOURCE_DIR}/src/*.cc)
file(GLOB headers ${PROJECT_SOURCE_DIR}/include/*.hh)


set(SRDIFFRACTION_MACROS
  vis.mac
  init.mac
  init_vis.mac
  run1.mac
  run2.mac
)

foreach(_macro ${SRDIFFRACTION_MACROS})
  configure_file(
    ${PROJECT_SOURCE_DIR}/${_macro}
    ${PROJECT_BINARY_DIR}/${_macro}
    COPYONLY
  )
endforeach()

# Добавляем исполняемый файл и связываем его с библиотеками Geant4
add_executable(${name} ${name}.cc ${sources} ${headers})
target_link_libraries(${name} ${Geant4_LIBRARIES} )

# Устанавливаем в директорию bin 
install(TARGETS ${name} DESTINATION bin)
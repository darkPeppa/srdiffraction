// =============================================================================
//  Config — полностью разрешённая конфигурация одного запуска.
//
//  Источник истины — YAML-файлы в config/. Python-оркестратор (liga_cli)
//  разрешает их (подставляет материалы, координаты слоёв, сетку, таблицы
//  источника) и передаёт сюда JSON. C++ ничего «не додумывает»: любое
//  отсутствующее обязательное поле — фатальная ошибка.
// =============================================================================
#pragma once

#include "HistoryFlags.hh"

#include <map>
#include <optional>
#include <string>
#include <vector>

namespace liga {

struct MaterialSpec {
  std::string name;
  std::string nist;                          // если задано — G4NistManager
  double density_g_cm3 = 0;                  // для смесей
  std::map<std::string, double> mass_fractions;  // элемент -> массовая доля
  std::map<std::string, int> atoms;              // элемент -> число атомов (альтернатива)
  std::string state = "solid";               // solid|gas
  double temperature_K = 293.15;
  double pressure_Pa = 101325.0;
};

struct HoleSpec {
  bool present = false;
  double size_x_um = 0;  // квадратное отверстие: size_x = size_y
  double size_y_um = 0;
  double center_x_um = 0;
  double center_y_um = 0;
};

struct LayerSpec {
  std::string name;          // уникальное имя объёма (например TestMembrane_Ti)
  Role role = Role::Other;
  std::string material;      // ключ в materials
  double thickness_um = 0;
  double z_front_mm = 0;     // координата передней (по пучку) грани
  double half_x_mm = 0;      // поперечный полуразмер
  double half_y_mm = 0;
  HoleSpec hole;             // отверстие (только для поглотителя)
  double prod_cut_um = -1;   // production cut региона (<0 — значение по умолчанию)
};

struct GridSpec {
  std::string name;
  std::vector<double> x_edges_um, y_edges_um, z_edges_um;  // z — от передней грани ПММА
  bool categories = true;   // хранить разложение по категориям и признакам
};

struct ScoringSpec {
  std::string pmma_layer = "PMMA";
  std::vector<GridSpec> grids;
  // Спектры фотонов, входящих в ПММА, и энерговыделения по энергии первичного фотона.
  double spectrum_emin_keV = 0.0, spectrum_emax_keV = 80.0;
  int spectrum_nbins = 400;
  // Областью "под отверстием" считаем |x|,|y| < hole/2 - margin; "под золотом" — |x|,|y| > hole/2 + margin.
  double region_margin_um = 5.0;
  // Плоскость записи фазового пространства (этап 1). Пусто — не пишем.
  bool phase_space_out = false;
  double phase_space_plane_z_mm = 0;
  std::string phase_space_file;  // префикс; каждый поток пишет <prefix>_t<N>.bin
  // Регистрация пропускания для тестов однородных пластин.
  bool slab_test = false;
  std::string slab_layer;
};

struct SourceSpec {
  // "sr_table"  — собственный генератор (режим B): таблица (E, psi, поляризация)
  // "phase_space" — фазовое пространство этапа 1 + локальное окно
  // "gps"       — G4GeneralParticleSource (режим A), команды в gps_macro
  // "pencil"    — моноэнергетический узкий пучок (тесты)
  std::string mode = "sr_table";
  std::string table_file;          // CSV: e_lo,e_hi,psi_lo,psi_hi,w_sigma,w_pi
  std::string phase_space_files;   // список через ';'
  std::string gps_macro;
  double pencil_energy_keV = 10.0;
  double z_mm = 0;                 // плоскость генерации
  double distance_m = 20.3;        // расстояние источник — плоскость генерации
  // Окно генерации (локальный пучок) и выборка по значимости вокруг отверстия.
  double window_half_x_mm = 1.0, window_half_y_mm = 1.0;
  double core_half_x_mm = 0.0, core_half_y_mm = 0.0;  // 0 — без выборки по значимости
  double core_fraction = 0.0;
  // Сканирование: "averaged" — усреднение по положению; "explicit" — явное
  // случайное положение сборки; "none" — неподвижный образец в медианной плоскости.
  std::string scan_mode = "averaged";
  double scan_half_amplitude_mm = 15.0;
  double hole_offset_x_mm = 0.0, hole_offset_y_mm = 0.0;  // положение отверстия в лабораторной СК
  // Размер источника и угловой разброс электронов (сигмы; см. docs/physics_model.md).
  double source_sigma_x_mm = 0.0, source_sigma_y_mm = 0.0;
  double electron_divergence_sigma_mrad = 0.0;
  bool polarization = true;
  // Этап 1: горизонтальная полуширина освещённой области (для весов «следа» пучка).
  double beam_half_x_mm = 36.0;
  // Этап 2 из фазового пространства: число первичных историй этапа 1.
  double ps_n_primaries = 0;
};

struct PhysicsSpec {
  std::string em = "livermore";   // livermore | livermore_polarized | penelope | option4 | standard
  bool fluo = true, auger = true, pixe = false, deexcitation_ignore_cut = true;
  double default_cut_um = 1.0;
  double lowest_electron_energy_eV = 100.0;
  double cuts_table_low_edge_eV = 100.0;
  // Ускорение: уничтожать e-/e+, которые гарантированно не достигнут ПММА
  // (консервативная оценка по пробегу; энергия учитывается в балансе).
  bool kill_unreachable_electrons = true;
  double pmma_max_step_um = 0;  // 0 — без ограничения
  // Редукция дисперсии: принудительное взаимодействие фотонов (G4BOptrForceCollision)
  // в объёмах указанных ролей. Пусто — аналоговый транспорт.
  std::vector<std::string> force_collision_roles;
};

struct RunSpec {
  std::string name = "run";
  std::string mode = "transport";  // transport | xs_table | geometry_check
  long long n_events = 1000;
  long seed = 12345;
  int threads = 0;                // 0 — по числу ядер
  std::string output;             // HDF5
  long long progress_every = 0;
  std::vector<double> xs_energies_keV;  // для mode=xs_table
  std::string xs_output;
};

struct Config {
  std::string raw_json;  // исходный JSON целиком (сохраняется в метаданных)
  RunSpec run;
  PhysicsSpec physics;
  SourceSpec source;
  ScoringSpec scoring;
  std::string world_material = "G4_Galactic";
  double world_half_xy_mm = 100, world_half_z_mm = 100;
  std::map<std::string, MaterialSpec> materials;
  std::vector<LayerSpec> layers;

  static Config Load(const std::string& path);
  const LayerSpec* FindLayer(const std::string& name) const;
};

// Глобальный доступ (конфигурация неизменна после загрузки, потокобезопасна для чтения).
const Config& Cfg();
void SetGlobalConfig(const Config& c);

}  // namespace liga

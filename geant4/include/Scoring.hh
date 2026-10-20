// =============================================================================
//  Scoring — накопители результатов одного потока (и итоговые на мастере).
//
//  VoxelScorer: энерговыделение в ячейках ПММА на неравномерной сетке.
//    • total, total_sq — сумма и сумма квадратов ПО ИСТОРИЯМ (не по шагам):
//      вклад события накапливается во временном буфере и возводится в квадрат
//      в конце события — это даёт корректную статистическую погрешность.
//    • cat[k]  — непересекающиеся категории (сумма по k == total);
//    • feat[i] — перекрывающиеся признаки (+ сумма квадратов для признака
//      «рассеяние в мембране» — его погрешность нужна для научного вывода).
//  ThreadData: все накопители потока + баланс энергии, спектры, тесты пластин,
//  запись фазового пространства.
// =============================================================================
#pragma once

#include "Config.hh"
#include "HistoryFlags.hh"

#include <array>
#include <cstdint>
#include <fstream>
#include <memory>
#include <string>
#include <vector>

namespace liga {

class VoxelScorer {
 public:
  explicit VoxelScorer(const GridSpec& g);
  // x,y — мм относительно центра; zrel — мм от передней грани ПММА.
  long Locate(double x, double y, double zrel) const;
  void Add(long idx, double e, Flags f);
  void EndEvent();
  void Merge(const VoxelScorer& o);

  const GridSpec& Spec() const { return fSpec; }
  long NVox() const { return fN; }
  int Nx() const { return fNx; }
  int Ny() const { return fNy; }
  int Nz() const { return fNz; }

  std::vector<double> total, total_sq, cat, feat, mem_sq;
  // Сумма квадратов по историям для колонок (x,y), просуммированных по всей глубине —
  // точная погрешность глубинно-усреднённых карт и профилей.
  std::vector<double> col_sq;

 private:
  static int Bin(const std::vector<double>& edges, double v);
  GridSpec fSpec;
  std::vector<double> fX, fY, fZ;  // в мм
  int fNx, fNy, fNz;
  long fN;
  std::vector<double> fEvtTot, fEvtMem, fEvtCol;
  std::vector<long> fTouched, fColTouched;
  std::vector<std::uint8_t> fIsColTouched;
  std::vector<std::uint8_t> fIsTouched;
};

// Запись фазового пространства (этап 1). Формат — docs/normalization.md, раздел PS.
#pragma pack(push, 1)
struct PSRecord {
  double e_keV, x_mm, y_mm, dx_mm, dy_mm, ux, uy, uz, px, py, pz, w, ylab_mm;
  std::uint32_t flags;
  std::int32_t pdg;
  std::int64_t event;
};
#pragma pack(pop)
static_assert(sizeof(PSRecord) == 13 * 8 + 4 + 4 + 8, "PSRecord layout");

struct ThreadData {
  explicit ThreadData(const Config& c);
  void EndEvent();
  void Merge(const ThreadData& o);

  std::vector<std::unique_ptr<VoxelScorer>> grids;

  // Регионы (по положению в плоскости xy относительно отверстия): 0 open, 1 edge, 2 shadow
  static constexpr int kNRegions = 3;
  // Классы фотонов на входе в ПММА: 0 без рассеяния, 1 рассеяние в мембране, 2 прочее рассеяние/вторичные
  static constexpr int kNEntryClasses = 3;
  int nE;
  double eMin, eMax;  // кэВ
  std::vector<double> entrySpec;     // [region][class][nE] — вес фотонов
  std::vector<double> entryEnergy;   // [region][class][nE] — переносимая энергия (МэВ*вес)
  std::vector<double> edepByPrimE;   // [region][nE] — Edep в ПММА по энергии первичного фотона (МэВ*вес)
  std::vector<double> edepByPrimEMem;// то же, только истории с рассеянием в мембране
  std::vector<double> regionEdep;    // [region][category]

  // Баланс энергии (МэВ*вес)
  double eIncident = 0, eEscape = 0, eKilledStack = 0, eKilledPlane = 0;
  std::vector<double> eDepByRole;  // [kNRoles]
  double sumW = 0, sumW2 = 0;      // веса первичных
  long long nEvents = 0;

  // Тест однородной пластины
  long long slabPrimaries = 0, slabUnscattered = 0;
  std::vector<long long> slabFirst;  // [4] Rayl, compt, phot, other

  // Фазовое пространство
  std::unique_ptr<std::ofstream> psOut;
  long long psCount = 0;
  double psSumW = 0;
  std::vector<PSRecord> psBuffer;
  void FlushPS();

  // Режим dump_primaries: E[кэВ], x,y,z[мм], ux,uy,uz, px,py,pz, w
  std::vector<std::array<double, 11>> primDump;

  int RegionOf(double x_mm, double y_mm) const;
  int EBin(double e_keV) const;

 private:
  double fHoleCx = 0, fHoleCy = 0, fHoleAx = -1, fHoleAy = -1, fMargin = 0;
};

}  // namespace liga

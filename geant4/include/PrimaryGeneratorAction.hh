// =============================================================================
//  PrimaryGeneratorAction — генераторы первичных фотонов.
//
//  Режим A ("gps")        — G4GeneralParticleSource, спектр из файла (макрос /gps/...).
//  Режим B ("sr_table")   — собственный генератор СИ: совместная таблица
//                           (энергия E, вертикальный угол излучения psi, поляризация
//                           sigma/pi) → коррелированные E, направление, поляризация;
//                           положение — в локальном окне вокруг отверстия
//                           (с выборкой по значимости и весами), сканирование —
//                           усреднённое или явное.
//  "phase_space"          — фазовое пространство этапа 1 (энергия, направление,
//                           поляризация, вес, метки истории), положение
//                           назначается заново по окну (трансляционная
//                           инвариантность однородных удалённых слоёв).
//  "pencil"               — моноэнергетический узкий пучок (тесты пластин).
// =============================================================================
#pragma once

#include "HistoryFlags.hh"

#include <G4ThreeVector.hh>
#include <G4VUserPrimaryGeneratorAction.hh>

#include <memory>
#include <vector>

class G4Event;
class G4GeneralParticleSource;
class G4ParticleDefinition;

namespace liga {

struct PSRecord;

// Совместная таблица (E, psi, pol), общая для всех потоков (только чтение).
struct SRTable {
  std::vector<double> eLo, eHi, psiLo, psiHi;  // кэВ, мрад
  std::vector<double> cdf;                     // по 2*rows (sigma, pi)
  // Колонки по psi (для неподвижного образца): индексы psi-бинов и их CDF.
  std::vector<double> psiEdges;                // уникальные границы psi
  std::vector<std::vector<int>> colRows;       // строки таблицы в каждом psi-бине
  std::vector<std::vector<double>> colCdf;     // CDF внутри колонки (по 2*nrows)
  double totalWeight = 0;
  static std::shared_ptr<const SRTable> Load(const std::string& path);
};

struct PhaseSpace {
  std::vector<PSRecord> rec;
  std::vector<double> cdf;  // по весам: выбираем записи пропорционально весу
  double sumW = 0;
  static std::shared_ptr<const PhaseSpace> Load(const std::string& filesSemicolon);
};

class PrimaryGeneratorAction : public G4VUserPrimaryGeneratorAction {
 public:
  PrimaryGeneratorAction();
  ~PrimaryGeneratorAction() override;
  void GeneratePrimaries(G4Event* ev) override;

 private:
  // Положение в окне: возвращает вес выборки по значимости.
  double SampleWindow(double& x, double& y) const;
  void Emit(G4Event* ev, double e, const G4ThreeVector& pos, const G4ThreeVector& dir, const G4ThreeVector& pol,
            double w, Flags flags, double yLab);

  std::unique_ptr<G4GeneralParticleSource> fGPS;
  std::shared_ptr<const SRTable> fTable;
  std::shared_ptr<const PhaseSpace> fPS;
  G4ParticleDefinition* fGamma = nullptr;
};

}  // namespace liga

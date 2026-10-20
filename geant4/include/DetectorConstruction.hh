// =============================================================================
//  DetectorConstruction — геометрия «стопка плоских слоёв вдоль +Z».
//
//  Все слои (окна, фильтр, исследуемая мембрана, основа шаблона, золотой
//  поглотитель с квадратным отверстием, каптон, ПММА, подложка) — боксы,
//  размещённые в мировом объёме по координатам из конфигурации.
//  Отверстие в золоте строится как 4 бокса-рамки (без булевых операций):
//  навигация точна и быстра, объёмы не перекрываются, а сплошная
//  титановая основа остаётся отдельным непрерывным объёмом.
//
//  Каждый логический объём получает свой G4Region (для production cuts)
//  и запись в таблице ролей (для классификации истории).
// =============================================================================
#pragma once

#include "HistoryFlags.hh"

#include <G4VUserDetectorConstruction.hh>
#include <globals.hh>

#include <map>
#include <vector>

class G4LogicalVolume;
class G4Material;
class G4VPhysicalVolume;

namespace liga {

struct LayerGeom {
  std::string name;
  Role role;
  double z_front, z_back;  // внутренние единицы Geant4 (мм)
  const G4Material* material;
};

class DetectorConstruction : public G4VUserDetectorConstruction {
 public:
  DetectorConstruction() = default;
  G4VPhysicalVolume* Construct() override;
  void ConstructSDandField() override;

  // Таблица ролей логических объёмов (только чтение после Construct).
  static Role RoleOf(const G4LogicalVolume* lv);
  static const std::vector<LayerGeom>& Layers();
  static const LayerGeom* PMMALayer();
  // Минимальная плотность среды между точкой z и передней гранью ПММА
  // (включая газовые промежутки) — для консервативного отсечения электронов.
  static const G4Material* LeastDenseMaterialBetween(double z_from, double z_to);

 private:
  G4Material* BuildMaterial(const std::string& key);
  std::map<std::string, G4Material*> fMaterials;
};

}  // namespace liga

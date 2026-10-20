#include "DetectorConstruction.hh"

#include "Config.hh"

#include <G4Box.hh>
#include <G4Element.hh>
#include <G4LogicalVolume.hh>
#include <G4Material.hh>
#include <G4NistManager.hh>
#include <G4PVPlacement.hh>
#include <G4ProductionCuts.hh>
#include <G4Region.hh>
#include <G4SystemOfUnits.hh>
#include <G4BOptrForceCollision.hh>
#include <G4UserLimits.hh>

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace liga {

namespace {
std::map<const G4LogicalVolume*, Role> gRoles;
std::vector<LayerGeom> gLayers;
const LayerGeom* gPMMA = nullptr;
const G4Material* gWorldMaterial = nullptr;
}  // namespace

G4Material* DetectorConstruction::BuildMaterial(const std::string& key) {
  if (auto it = fMaterials.find(key); it != fMaterials.end()) return it->second;
  auto* nist = G4NistManager::Instance();
  G4Material* mat = nullptr;
  const auto& mats = Cfg().materials;
  auto it = mats.find(key);
  if (it == mats.end()) {
    // Прямая ссылка на материал NIST по имени (например G4_Galactic).
    mat = nist->FindOrBuildMaterial(key);
    if (!mat) throw std::runtime_error("unknown material " + key);
  } else {
    const MaterialSpec& m = it->second;
    const G4State state = (m.state == "gas") ? kStateGas : kStateSolid;
    if (!m.nist.empty()) {
      G4Material* base = nist->FindOrBuildMaterial(m.nist);
      if (!base) throw std::runtime_error("unknown NIST material " + m.nist);
      if (m.density_g_cm3 > 0 && std::abs(m.density_g_cm3 - base->GetDensity() / (g / cm3)) > 1e-9) {
        // Тот же состав, другая плотность (например стеклоуглерод 1.49 г/см3 на базе G4_C).
        mat = nist->BuildMaterialWithNewDensity("LIGA_" + key, m.nist, m.density_g_cm3 * g / cm3,
                                                m.temperature_K * kelvin, m.pressure_Pa * pascal);
      } else {
        mat = base;
      }
    } else if (!m.atoms.empty()) {
      mat = new G4Material("LIGA_" + key, m.density_g_cm3 * g / cm3, (G4int)m.atoms.size(), state,
                           m.temperature_K * kelvin, m.pressure_Pa * pascal);
      for (const auto& [el, n] : m.atoms) mat->AddElement(nist->FindOrBuildElement(el), n);
    } else if (!m.mass_fractions.empty()) {
      double sum = 0;
      for (const auto& kv : m.mass_fractions) sum += kv.second;
      if (std::abs(sum - 1.0) > 1e-3)
        throw std::runtime_error("material " + key + ": mass fractions sum to " + std::to_string(sum));
      mat = new G4Material("LIGA_" + key, m.density_g_cm3 * g / cm3, (G4int)m.mass_fractions.size(), state,
                           m.temperature_K * kelvin, m.pressure_Pa * pascal);
      for (const auto& [el, f] : m.mass_fractions) mat->AddElement(nist->FindOrBuildElement(el), f / sum);
    } else {
      throw std::runtime_error("material " + key + " has neither nist, atoms nor mass_fractions");
    }
  }
  fMaterials[key] = mat;
  return mat;
}

G4VPhysicalVolume* DetectorConstruction::Construct() {
  const Config& c = Cfg();
  gRoles.clear();
  gLayers.clear();
  gPMMA = nullptr;

  G4Material* worldMat = BuildMaterial(c.world_material);
  gWorldMaterial = worldMat;
  auto* worldS = new G4Box("World", c.world_half_xy_mm * mm, c.world_half_xy_mm * mm, c.world_half_z_mm * mm);
  auto* worldL = new G4LogicalVolume(worldS, worldMat, "World");
  auto* worldP = new G4PVPlacement(nullptr, {}, worldL, "World", nullptr, false, 0, false);
  gRoles[worldL] = Role::Gas;

  for (const LayerSpec& ls : c.layers) {
    G4Material* mat = BuildMaterial(ls.material);
    const double t = ls.thickness_um * um;
    const double z0 = ls.z_front_mm * mm;
    const double zc = z0 + 0.5 * t;
    const double hx = ls.half_x_mm * mm, hy = ls.half_y_mm * mm;
    if (z0 < -c.world_half_z_mm * mm || z0 + t > c.world_half_z_mm * mm || hx > c.world_half_xy_mm * mm ||
        hy > c.world_half_xy_mm * mm)
      throw std::runtime_error("layer " + ls.name + " does not fit into the world volume");

    auto* region = new G4Region(ls.name);
    if (ls.prod_cut_um > 0) {
      auto* cuts = new G4ProductionCuts();
      cuts->SetProductionCut(ls.prod_cut_um * um);
      region->SetProductionCuts(cuts);
    }

    std::vector<G4LogicalVolume*> lvs;
    if (!ls.hole.present) {
      auto* s = new G4Box(ls.name, hx, hy, 0.5 * t);
      auto* lv = new G4LogicalVolume(s, mat, ls.name);
      new G4PVPlacement(nullptr, {0, 0, zc}, lv, ls.name, worldL, false, 0, false);
      lvs.push_back(lv);
    } else {
      // Рамка из 4 боксов вокруг квадратного (прямоугольного) окна.
      const double ax = 0.5 * ls.hole.size_x_um * um, ay = 0.5 * ls.hole.size_y_um * um;
      const double cx = ls.hole.center_x_um * um, cy = ls.hole.center_y_um * um;
      if (cx - ax <= -hx || cx + ax >= hx || cy - ay <= -hy || cy + ay >= hy)
        throw std::runtime_error("hole of layer " + ls.name + " does not fit into the layer");
      struct Piece { const char* tag; double x0, x1, y0, y1; };
      const Piece pieces[4] = {{"L", -hx, cx - ax, -hy, hy},
                               {"R", cx + ax, hx, -hy, hy},
                               {"B", cx - ax, cx + ax, -hy, cy - ay},
                               {"T", cx - ax, cx + ax, cy + ay, hy}};
      for (const auto& p : pieces) {
        const std::string n = ls.name + "_" + p.tag;
        auto* s = new G4Box(n, 0.5 * (p.x1 - p.x0), 0.5 * (p.y1 - p.y0), 0.5 * t);
        auto* lv = new G4LogicalVolume(s, mat, n);
        new G4PVPlacement(nullptr, {0.5 * (p.x0 + p.x1), 0.5 * (p.y0 + p.y1), zc}, lv, n, worldL, false, 0, false);
        lvs.push_back(lv);
      }
    }
    for (auto* lv : lvs) {
      gRoles[lv] = ls.role;
      region->AddRootLogicalVolume(lv);
      if (ls.role == Role::PMMA && c.physics.pmma_max_step_um > 0)
        lv->SetUserLimits(new G4UserLimits(c.physics.pmma_max_step_um * um));
    }
    gLayers.push_back({ls.name, ls.role, z0, z0 + t, mat});
  }

  for (const auto& l : gLayers)
    if (l.name == c.scoring.pmma_layer) gPMMA = &l;

  // Проверка: слои не должны перекрываться по z (поперечно они все центрированы).
  std::vector<LayerGeom> sorted = gLayers;
  std::sort(sorted.begin(), sorted.end(), [](auto& a, auto& b) { return a.z_front < b.z_front; });
  for (size_t i = 1; i < sorted.size(); ++i)
    if (sorted[i].z_front < sorted[i - 1].z_back - 1e-9 * mm)
      throw std::runtime_error("layers overlap along z: " + sorted[i - 1].name + " / " + sorted[i].name);

  return worldP;
}

void DetectorConstruction::ConstructSDandField() {
  // Операторы смещения — потоколокальные, поэтому создаются здесь (вызывается в каждом потоке).
  const auto& roles = Cfg().physics.force_collision_roles;
  if (roles.empty()) return;
  auto* op = new G4BOptrForceCollision("gamma", "liga_force_collision");
  int attached = 0;
  for (const auto& [lv, role] : gRoles)
    for (const auto& r : roles)
      if (RoleFromString(r) == role) {
        op->AttachTo(lv);
        ++attached;
      }
  if (!attached) G4Exception("DetectorConstruction", "BIAS01", JustWarning, "force_collision: no volume matched");
}

Role DetectorConstruction::RoleOf(const G4LogicalVolume* lv) {
  auto it = gRoles.find(lv);
  return it == gRoles.end() ? Role::Other : it->second;
}

const std::vector<LayerGeom>& DetectorConstruction::Layers() { return gLayers; }
const LayerGeom* DetectorConstruction::PMMALayer() { return gPMMA; }

const G4Material* DetectorConstruction::LeastDenseMaterialBetween(double z_from, double z_to) {
  // Слои занимают только часть интервала — промежутки заполнены мировым газом.
  const G4Material* best = nullptr;
  double covered = 0;
  for (const auto& l : gLayers) {
    const double a = std::max(z_from, l.z_front), b = std::min(z_to, l.z_back);
    if (b > a) {
      covered += b - a;
      if (!best || l.material->GetDensity() < best->GetDensity()) best = l.material;
    }
  }
  if (covered < (z_to - z_from) * (1 - 1e-9) || !best) {
    if (!best || gWorldMaterial->GetDensity() < best->GetDensity()) best = gWorldMaterial;
  }
  return best;
}

}  // namespace liga

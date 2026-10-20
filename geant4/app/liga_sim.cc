// =============================================================================
//  liga_sim — приложение Geant4 для моделирования прохождения СИ ВЭПП-3
//  через фильтры, мембраны рентгеношаблонов и ПММА.
//
//  Использование:  liga_sim <resolved_config.json>
//  Режимы (run.mode):
//    transport       — транспорт частиц и запись результатов в HDF5;
//    xs_table        — таблица коэффициентов взаимодействия фотонов (G4EmCalculator)
//                      для всех материалов конфигурации (сверка с NIST);
//    geometry_check  — проверка перекрытий и зондирование навигатором.
//  Конфигурацию готовит Python-оркестратор (`liga simulate ...`).
// =============================================================================
#include "Actions.hh"
#include "Config.hh"
#include "DetectorConstruction.hh"
#include "PhysicsList.hh"

#include <G4EmCalculator.hh>
#include <G4Electron.hh>
#include <G4Gamma.hh>
#include <G4LogicalVolume.hh>
#include <G4Material.hh>
#include <G4Navigator.hh>
#include <G4PhysicalVolumeStore.hh>
#include <G4RunManager.hh>
#include <G4RunManagerFactory.hh>
#include <G4SystemOfUnits.hh>
#include <G4Threading.hh>
#include <G4TransportationManager.hh>
#include <G4UImanager.hh>
#include <Randomize.hh>

#include <cstdlib>
#include <fstream>
#include <iostream>
#include <set>

using namespace liga;

namespace {

int ThreadsFromConfig() {
  int n = Cfg().run.threads;
  if (n <= 0) {
    if (const char* e = std::getenv("LIGA_THREADS")) n = std::atoi(e);
  }
  if (n <= 0) n = G4Threading::G4GetNumberOfCores();
  return std::max(1, n);
}

int RunXsTable(G4RunManager* rm) {
  rm->BeamOn(0);  // построение физических таблиц
  const Config& c = Cfg();
  std::ofstream out(c.run.xs_output);
  out << "# photon interaction coefficients from Geant4 G4EmCalculator, physics=" << c.physics.em << "\n";
  out << "material,density_g_cm3,energy_keV,mu_phot_cm,mu_compt_cm,mu_rayl_cm,mu_conv_cm,mu_total_cm,mu_rho_total_cm2_g,"
         "electron_csda_range_um\n";
  G4EmCalculator calc;
  std::set<const G4Material*> seen;
  for (const auto& l : DetectorConstruction::Layers()) {
    const G4Material* m = l.material;
    if (!seen.insert(m).second) continue;
    const double rho = m->GetDensity() / (g / cm3);
    for (double ek : c.run.xs_energies_keV) {
      const double E = ek * keV;
      double mu[4];
      const char* procs[4] = {"phot", "compt", "Rayl", "conv"};
      double tot = 0;
      for (int i = 0; i < 4; ++i) {
        mu[i] = calc.ComputeCrossSectionPerVolume(E, G4Gamma::Definition(), procs[i], m) * cm;
        tot += mu[i];
      }
      const double rng = calc.GetCSDARange(E, G4Electron::Definition(), m) / um;
      out << l.name << "," << rho << "," << ek << "," << mu[0] << "," << mu[1] << "," << mu[2] << "," << mu[3] << ","
          << tot << "," << tot / rho << "," << rng << "\n";
    }
  }
  G4cout << "[liga] wrote " << c.run.xs_output << G4endl;
  return 0;
}

int RunGeometryCheck() {
  const Config& c = Cfg();
  int overlaps = 0, checked = 0;
  for (auto* pv : *G4PhysicalVolumeStore::GetInstance()) {
    if (pv->GetMotherLogical() == nullptr) continue;
    ++checked;
    if (pv->CheckOverlaps(2000, 0.0, false, 1)) ++overlaps;
  }
  G4Navigator* nav = G4TransportationManager::GetTransportationManager()->GetNavigatorForTracking();
  std::ofstream out(c.run.output);
  out << "{\n  \"checked_volumes\": " << checked << ",\n  \"overlaps\": " << overlaps << ",\n  \"probes\": [\n";
  bool first = true;
  auto probe = [&](const std::string& label, double x, double y, double z) {
    const G4VPhysicalVolume* pv = nav->LocateGlobalPointAndSetup({x, y, z}, nullptr, false, true);
    const std::string mat = pv ? pv->GetLogicalVolume()->GetMaterial()->GetName() : "none";
    const std::string vol = pv ? pv->GetName() : "none";
    out << (first ? "" : ",\n") << "    {\"label\": \"" << label << "\", \"x_mm\": " << x / mm << ", \"y_mm\": " << y / mm
        << ", \"z_mm\": " << z / mm << ", \"volume\": \"" << vol << "\", \"material\": \"" << mat << "\"}";
    first = false;
  };
  for (const auto& l : c.layers) {
    const double t = l.thickness_um * um, z0 = l.z_front_mm * mm;
    double x = 0;
    if (l.hole.present) {
      const double ax = 0.5 * l.hole.size_x_um * um + l.hole.center_x_um * um;
      x = ax + 0.5 * (l.half_x_mm * mm - ax);
      probe(l.name + ":hole_center", l.hole.center_x_um * um, l.hole.center_y_um * um, z0 + 0.5 * t);
    }
    probe(l.name + ":center", x, 0, z0 + 0.5 * t);
    probe(l.name + ":front_inside", x, 0, z0 + 1e-3 * t);
    probe(l.name + ":back_inside", x, 0, z0 + (1 - 1e-3) * t);
  }
  out << "\n  ]\n}\n";
  G4cout << "[liga] geometry check: " << checked << " volumes, " << overlaps << " overlaps" << G4endl;
  return overlaps ? 2 : 0;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) {
    std::cerr << "usage: liga_sim <resolved_config.json>\n";
    return 1;
  }
  try {
    SetGlobalConfig(Config::Load(argv[1]));
  } catch (const std::exception& e) {
    std::cerr << "[liga] configuration error: " << e.what() << "\n";
    return 1;
  }
  const Config& c = Cfg();
  G4Random::setTheSeed(c.run.seed);

  const bool transport = c.run.mode == "transport" || c.run.mode == "dump_primaries";
  const int nThreads = transport ? ThreadsFromConfig() : 1;
  auto* rm = G4RunManagerFactory::CreateRunManager(G4RunManagerType::MTOnly, nThreads);
  rm->SetNumberOfThreads(nThreads);
  auto* ui = G4UImanager::GetUIpointer();
  ui->ApplyCommand("/control/verbose 0");
  ui->ApplyCommand("/run/verbose 0");
  ui->ApplyCommand("/event/verbose 0");
  ui->ApplyCommand("/tracking/verbose 0");

  int rc = 0;
  try {
    rm->SetUserInitialization(new DetectorConstruction());
    rm->SetUserInitialization(new PhysicsList());
    rm->SetUserInitialization(new ActionInitialization());
    rm->Initialize();
    if (c.run.mode == "xs_table") {
      rc = RunXsTable(rm);
    } else if (c.run.mode == "geometry_check") {
      rc = RunGeometryCheck();
    } else if (transport) {
      if (c.source.mode == "gps") ui->ApplyCommand("/control/execute " + c.source.gps_macro);
      G4cout << "[liga] run '" << c.run.name << "': " << c.run.n_events << " events, " << nThreads << " threads, physics "
             << c.physics.em << G4endl;
      rm->BeamOn(G4int(c.run.n_events));
    } else {
      std::cerr << "[liga] unknown run.mode " << c.run.mode << "\n";
      rc = 1;
    }
  } catch (const std::exception& e) {
    std::cerr << "[liga] error: " << e.what() << "\n";
    rc = 1;
  }
  delete rm;
  return rc;
}

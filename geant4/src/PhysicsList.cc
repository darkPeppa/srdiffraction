#include "PhysicsList.hh"

#include "Config.hh"

#include <G4EmLivermorePhysics.hh>
#include <G4EmLivermorePolarizedPhysics.hh>
#include <G4EmParameters.hh>
#include <G4EmPenelopePhysics.hh>
#include <G4EmStandardPhysics.hh>
#include <G4EmStandardPhysics_option4.hh>
#include <G4GenericBiasingPhysics.hh>
#include <G4ProductionCutsTable.hh>
#include <G4StepLimiterPhysics.hh>
#include <G4SystemOfUnits.hh>

#include <stdexcept>

namespace liga {

PhysicsList::PhysicsList() {
  const PhysicsSpec& p = Cfg().physics;
  SetVerboseLevel(0);
  if (p.em == "livermore") RegisterPhysics(new G4EmLivermorePhysics(0));
  else if (p.em == "livermore_polarized") RegisterPhysics(new G4EmLivermorePolarizedPhysics(0));
  else if (p.em == "penelope") RegisterPhysics(new G4EmPenelopePhysics(0));
  else if (p.em == "option4") RegisterPhysics(new G4EmStandardPhysics_option4(0));
  else if (p.em == "standard") RegisterPhysics(new G4EmStandardPhysics(0));
  else throw std::runtime_error("unknown physics.em = " + p.em);
  if (p.pmma_max_step_um > 0) RegisterPhysics(new G4StepLimiterPhysics());
  if (!p.force_collision_roles.empty()) {
    auto* bias = new G4GenericBiasingPhysics();
    bias->Bias("gamma");
    RegisterPhysics(bias);
  }

  // Параметры задаются ПОСЛЕ конструкторов (они выставляют свои значения по умолчанию).
  auto* em = G4EmParameters::Instance();
  em->SetFluo(p.fluo);
  em->SetAuger(p.auger);
  em->SetPixe(p.pixe);
  em->SetDeexcitationIgnoreCut(p.deexcitation_ignore_cut);
  em->SetLowestElectronEnergy(p.lowest_electron_energy_eV * eV);
  em->SetBuildCSDARange(true);
  em->SetVerbose(0);
  SetDefaultCutValue(p.default_cut_um * um);
}

void PhysicsList::SetCuts() {
  G4ProductionCutsTable::GetProductionCutsTable()->SetEnergyRange(Cfg().physics.cuts_table_low_edge_eV * eV,
                                                                   100 * GeV);
  G4VUserPhysicsList::SetCuts();
}

}  // namespace liga

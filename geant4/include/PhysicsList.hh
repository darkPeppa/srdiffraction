// =============================================================================
//  PhysicsList — электромагнитная физика низких энергий.
//
//  Варианты (physics.em): livermore (основной), livermore_polarized,
//  penelope, option4, standard (= QBBC/opt0, для сверки с G4beamline).
//  Атомная релаксация: флуоресценция + оже-каскад, PIXE выкл.,
//  deexcitationIgnoreCut — продукты релаксации рождаются независимо от порогов.
// =============================================================================
#pragma once

#include <G4VModularPhysicsList.hh>

namespace liga {

class PhysicsList : public G4VModularPhysicsList {
 public:
  PhysicsList();
  void SetCuts() override;
};

}  // namespace liga

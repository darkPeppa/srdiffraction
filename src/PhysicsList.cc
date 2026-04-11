#include "PhysicsList.hh"
#include "G4EmStandardPhysics.hh"
#include "G4OpticalPhysics.hh"  // если нужна оптика, но можно без неё
#include "G4DecayPhysics.hh"
#include "G4RadioactiveDecayPhysics.hh"
#include "G4EmLivermorePhysics.hh"

PhysicsList::PhysicsList()
{
    RegisterPhysics(new G4EmLivermorePhysics());
}

PhysicsList::~PhysicsList()
{}
#include "PrimaryGeneratorAction.hh"
#include "G4Event.hh"
#include "G4ParticleTable.hh"
#include "G4ParticleDefinition.hh"
#include "G4SystemOfUnits.hh"
#include "Randomize.hh"

PrimaryGeneratorAction::PrimaryGeneratorAction()
{
    G4int n_particle = 1;
    fParticleGun = new G4ParticleGun(n_particle);

    // Задаём гамма-квант
    G4ParticleTable* particleTable = G4ParticleTable::GetParticleTable();
    G4ParticleDefinition* gamma = particleTable->FindParticle("gamma");

    fParticleGun->SetParticleDefinition(gamma);
    // Match beamline reference energy.
    fParticleGun->SetParticleEnergy(5.3 * keV);
    fParticleGun->SetParticlePosition(G4ThreeVector(0, 0, -1.0 * mm));
    fParticleGun->SetParticleMomentumDirection(G4ThreeVector(0, 0, 1)); // along +z
}

PrimaryGeneratorAction::~PrimaryGeneratorAction()
{
    delete fParticleGun;
}

void PrimaryGeneratorAction::GeneratePrimaries(G4Event* event)
{
    // Beamline-like angular Gaussian spread:
    // sigmaXp = sigmaYp = 0.00026 rad.
    const G4double sigmaAngle = 0.00026;
    const G4double xp = G4RandGauss::shoot(0.0, sigmaAngle);
    const G4double yp = G4RandGauss::shoot(0.0, sigmaAngle);
    G4ThreeVector dir(xp, yp, 1.0);
    dir = dir.unit();

    fParticleGun->SetParticlePosition(G4ThreeVector(0, 0, -1.0 * mm));
    fParticleGun->SetParticleMomentumDirection(dir);
    fParticleGun->GeneratePrimaryVertex(event);
}
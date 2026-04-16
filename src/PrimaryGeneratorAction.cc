#include "PrimaryGeneratorAction.hh"
#include "G4Event.hh"
#include "G4ParticleTable.hh"
#include "G4ParticleDefinition.hh"
#include "G4SystemOfUnits.hh"
#include "Randomize.hh"
#include <cmath>

PrimaryGeneratorAction::PrimaryGeneratorAction()
{
    G4int n_particle = 1;
    fParticleGun = new G4ParticleGun(n_particle);

    // Задаём гамма-квант
    G4ParticleTable* particleTable = G4ParticleTable::GetParticleTable();
    G4ParticleDefinition* gamma = particleTable->FindParticle("gamma");

    fParticleGun->SetParticleDefinition(gamma);
    fParticleGun->SetParticleEnergy(3.5 * keV);

    // Позиция источника выше верхней границы золота.
    // Это задаёт порядок пролёта: Gold -> Beryllium -> PMMA.
    fParticleGun->SetParticlePosition(G4ThreeVector(0, 0, -4.7 * mm));
    fParticleGun->SetParticleMomentumDirection(G4ThreeVector(0, 0, -1)); // вниз
}

PrimaryGeneratorAction::~PrimaryGeneratorAction()
{
    delete fParticleGun;
}

void PrimaryGeneratorAction::GeneratePrimaries(G4Event* event)
{
    // Gaussian source centered above the gold region.
    // Most particles hit near center, tails become rarer further away.
    const G4double halfPlateSize = 1.5 * mm;
    const G4double sigma = 10.0 * um;

    G4double x0 = 0.0;
    G4double y0 = 0.0;
    do {
        x0 = G4RandGauss::shoot(0.0, sigma);
        y0 = G4RandGauss::shoot(0.0, sigma);
    } while (std::abs(x0) > halfPlateSize || std::abs(y0) > halfPlateSize);

    // Start above gold and move downward through the full stack.
    const G4double z0 = -4.7 * mm;

    fParticleGun->SetParticlePosition(G4ThreeVector(x0, y0, z0));
    fParticleGun->GeneratePrimaryVertex(event);
}
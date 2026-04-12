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
    fParticleGun->SetParticleEnergy(15.0 * keV);

    // Позиция источника: над центром золотого слоя (смещение по Z, чтобы летел сверху)
    // Золотой слой находится на высоте ~ -4.9835 мм от центра мира, но проще задать позицию в мировой системе.
    // Мы знаем, что верхняя грань золота примерно на Z = -4.971 мм (см. расчёты в DetectorConstruction).
    // Поставим источник на Z = -4.8 мм, т.е. прямо над слоем.
    // Упростим: пусть источник будет на Z = -4.9 мм (внутри мира). Направим вертикально вниз.
    fParticleGun->SetParticlePosition(G4ThreeVector(0, 0, -4.9 * mm));
    fParticleGun->SetParticleMomentumDirection(G4ThreeVector(0, 0, -1)); // вниз
}

PrimaryGeneratorAction::~PrimaryGeneratorAction()
{
    delete fParticleGun;
}

void PrimaryGeneratorAction::GeneratePrimaries(G4Event* event)
{
    // Uniform source spot over the PMMA plate surface: 3x3 mm.
    const G4double halfPlateSize = 1.5 * mm;
    const G4double x0 = (2.0 * G4UniformRand() - 1.0) * halfPlateSize;
    const G4double y0 = (2.0 * G4UniformRand() - 1.0) * halfPlateSize;
    const G4double z0 = -4.9 * mm;

    fParticleGun->SetParticlePosition(G4ThreeVector(x0, y0, z0));
    fParticleGun->GeneratePrimaryVertex(event);
}
#include "SensitiveDetector.hh"
#include "PMMAHit.hh"
#include "G4Step.hh"
#include "G4TouchableHistory.hh"
#include "G4SDManager.hh"

PMMASensitiveDetector::PMMASensitiveDetector(const G4String& name)
    : G4VSensitiveDetector(name), fHCID(-1)
{
    collectionName.insert("PMMAHitsCollection");
}

PMMASensitiveDetector::~PMMASensitiveDetector()
{}

void PMMASensitiveDetector::Initialize(G4HCofThisEvent* hce)
{
    fHitsCollection = new PMMAHitsCollection(SensitiveDetectorName, collectionName[0]);
    if (fHCID < 0)
        fHCID = G4SDManager::GetSDMpointer()->GetCollectionID(collectionName[0]);
    hce->AddHitsCollection(fHCID, fHitsCollection);
}

G4bool PMMASensitiveDetector::ProcessHits(G4Step* step, G4TouchableHistory*)
{
    G4StepPoint* prePoint = step->GetPreStepPoint();
    if (!prePoint) {
        return false;
    }

    // Beamline-like scoring: one entry when track crosses PMMA boundary.
    if (prePoint->GetStepStatus() != fGeomBoundary) {
        return false;
    }

    G4double edep = step->GetTotalEnergyDeposit();
    // Получаем позицию внутри объёма PMMA в локальной системе координат.
    G4ThreeVector worldPos = prePoint->GetPosition();
    // Преобразуем в локальные координаты объёма PMMA
    G4TouchableHandle touchable = prePoint->GetTouchableHandle();
    if (!touchable) {
        return false;
    }
    G4ThreeVector localPos = touchable->GetHistory()->GetTopTransform().TransformPoint(worldPos);

    PMMAHit* hit = new PMMAHit();
    hit->SetPos(localPos);
    hit->SetEdep(edep);
    fHitsCollection->insert(hit);
    return true;
}

void PMMASensitiveDetector::EndOfEvent(G4HCofThisEvent*)
{
    // Можно оставить пустым, т.к. данные уже собраны в хиты
}
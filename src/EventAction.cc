#include "EventAction.hh"
#include "RunAction.hh"
#include "PMMAHit.hh"
#include "G4Event.hh"
#include "G4SDManager.hh"
#include "G4HCofThisEvent.hh"
#include "G4RunManager.hh"
#include "G4SystemOfUnits.hh"

EventAction::EventAction()
    : fPMMAHCID(-1)
{}

EventAction::~EventAction()
{}

void EventAction::BeginOfEventAction(const G4Event*)
{}

void EventAction::EndOfEventAction(const G4Event* event)
{
    if (!event) {
        return;
    }

    G4double eventEdepKeV = 0.;
    G4double weightedXmmTimesE = 0.;
    G4double weightedYmmTimesE = 0.;
    G4double weightedZmmTimesE = 0.;

    G4HCofThisEvent* hce = event->GetHCofThisEvent();
    PMMAHitsCollection* hitsCollection = nullptr;
    if (hce) {
        if (fPMMAHCID < 0) {
            G4SDManager* sdManager = G4SDManager::GetSDMpointer();
            fPMMAHCID = sdManager->GetCollectionID("PMMAHitsCollection");
        }

        if (fPMMAHCID >= 0) {
            hitsCollection = static_cast<PMMAHitsCollection*>(hce->GetHC(fPMMAHCID));
        }
    }

    RunAction* runAction = const_cast<RunAction*>(static_cast<const RunAction*>(G4RunManager::GetRunManager()->GetUserRunAction()));
    if (!runAction) {
        return;
    }

    if (hitsCollection) {
        runAction->FillHistogram(hitsCollection);

        const G4int nHits = hitsCollection->GetSize();
        for (G4int i = 0; i < nHits; ++i) {
            PMMAHit* hit = (*hitsCollection)[i];
            const G4double hitEdepKeV = hit->GetEdep() / keV;
            eventEdepKeV += hitEdepKeV;

            const G4ThreeVector pos = hit->GetPos();
            weightedXmmTimesE += (pos.x() / mm) * hitEdepKeV;
            weightedYmmTimesE += (pos.y() / mm) * hitEdepKeV;
            weightedZmmTimesE += (pos.z() / mm) * hitEdepKeV;
        }
    }

    if (eventEdepKeV > 0.) {
        const G4double x_mm = weightedXmmTimesE / eventEdepKeV;
        const G4double y_mm = weightedYmmTimesE / eventEdepKeV;
        const G4double z_mm = weightedZmmTimesE / eventEdepKeV;
        runAction->FillEventTable(x_mm, y_mm, z_mm, eventEdepKeV);
    }
}

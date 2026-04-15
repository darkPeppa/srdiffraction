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

    G4double x_mm = 0.;
    G4double y_mm = 0.;
    if (const auto* primaryVertex = event->GetPrimaryVertex(0)) {
        x_mm = primaryVertex->GetX0() / mm;
        y_mm = primaryVertex->GetY0() / mm;
    }

    G4double eventEdepKeV = 0.;

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
            eventEdepKeV += (*hitsCollection)[i]->GetEdep() / keV;
        }
    }

    runAction->FillEventTable(x_mm, y_mm, eventEdepKeV);
}

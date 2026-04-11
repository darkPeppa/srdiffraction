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

    G4HCofThisEvent* hce = event->GetHCofThisEvent();
    if (!hce) {
        return;
    }

    if (fPMMAHCID < 0) {
        G4SDManager* sdManager = G4SDManager::GetSDMpointer();
        fPMMAHCID = sdManager->GetCollectionID("PMMAHitsCollection");
        if (fPMMAHCID < 0) {
            return;
        }
    }

    auto* hitsCollection = static_cast<PMMAHitsCollection*>(hce->GetHC(fPMMAHCID));
    if (!hitsCollection) {
        return;
    }

    // Передаём хиты в RunAction для заполнения гистограммы
    // (RunAction должен быть статически доступен или передан через указатель)
    // Для простоты сделаем глобальный указатель или используем Singleton.
    // Но корректнее передать через G4RunManager.
    // Здесь я создам статический метод в RunAction для доступа.
    RunAction* runAction = const_cast<RunAction*>(static_cast<const RunAction*>(G4RunManager::GetRunManager()->GetUserRunAction()));
    if (runAction)
        runAction->FillHistogram(hitsCollection);
}
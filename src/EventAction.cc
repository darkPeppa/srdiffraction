#include "EventAction.hh"
#include "RunAction.hh"
#include "PMMAHit.hh"
#include "G4Event.hh"
#include "G4SDManager.hh"
#include "G4HCofThisEvent.hh"
#include "G4RunManager.hh"
#include "G4SystemOfUnits.hh"

EventAction::EventAction()
{}

EventAction::~EventAction()
{}

void EventAction::BeginOfEventAction(const G4Event*)
{}

void EventAction::EndOfEventAction(const G4Event* event)
{
    // Получаем хиты из чувствительного детектора PMMA
    G4SDManager* sdManager = G4SDManager::GetSDMpointer();
    G4int collID = sdManager->GetCollectionID("PMMAHitsCollection");
    auto hitsCollection = (PMMAHitsCollection*)event->GetHCofThisEvent()->GetHC(collID);

    if (!hitsCollection) return;

    // Передаём хиты в RunAction для заполнения гистограммы
    // (RunAction должен быть статически доступен или передан через указатель)
    // Для простоты сделаем глобальный указатель или используем Singleton.
    // Но корректнее передать через G4RunManager.
    // Здесь я создам статический метод в RunAction для доступа.
    RunAction* runAction = const_cast<RunAction*>(static_cast<const RunAction*>(G4RunManager::GetRunManager()->GetUserRunAction()));
    if (runAction)
        runAction->FillHistogram(hitsCollection);
}
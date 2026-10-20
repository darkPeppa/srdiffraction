// =============================================================================
//  Пользовательские действия Geant4.
//
//  RunAction      — владеет ThreadData потока; рабочие потоки сливают свои
//                   данные в мастер (под мьютексом), мастер пишет HDF5.
//  EventAction    — закрывает событие (суммы квадратов по историям).
//  TrackingAction — назначает метки первичным трекам.
//  SteppingAction — регистрация энерговыделения, меток рассеяния, наследование
//                   меток вторичными частицами, баланс энергии, спектры,
//                   плоскость фазового пространства, тесты пластин.
//  StackingAction — отсечение электронов, которые не могут достичь ПММА
//                   (консервативно по CSDA-пробегу в наименее плотной среде).
// =============================================================================
#pragma once

#include "Scoring.hh"

#include <G4UserEventAction.hh>
#include <G4UserRunAction.hh>
#include <G4UserStackingAction.hh>
#include <G4UserSteppingAction.hh>
#include <G4UserTrackingAction.hh>
#include <G4VUserActionInitialization.hh>

#include <chrono>
#include <memory>

class G4EmCalculator;

namespace liga {

class RunAction : public G4UserRunAction {
 public:
  explicit RunAction(bool master);
  ~RunAction() override;
  void BeginOfRunAction(const G4Run*) override;
  void EndOfRunAction(const G4Run*) override;
  ThreadData* Data() { return fData.get(); }

 private:
  bool fMaster;
  std::unique_ptr<ThreadData> fData;
  std::chrono::steady_clock::time_point fStart;
};

class EventAction : public G4UserEventAction {
 public:
  explicit EventAction(RunAction* r) : fRun(r) {}
  void BeginOfEventAction(const G4Event*) override {}
  void EndOfEventAction(const G4Event*) override;

 private:
  RunAction* fRun;
};

class TrackingAction : public G4UserTrackingAction {
 public:
  explicit TrackingAction(RunAction* r) : fRun(r) {}
  void PreUserTrackingAction(const G4Track*) override;

 private:
  RunAction* fRun;
};

class SteppingAction : public G4UserSteppingAction {
 public:
  explicit SteppingAction(RunAction* r);
  void UserSteppingAction(const G4Step*) override;

 private:
  RunAction* fRun;
  double fPMMAFront = 0, fPMMABack = 0;
  bool fHavePMMA = false;
  double fSlabFront = 0, fSlabBack = 0;
  bool fSlab = false;
  bool fPlane = false;
  double fPlaneZ = 0;
};

class StackingAction : public G4UserStackingAction {
 public:
  explicit StackingAction(RunAction* r);
  ~StackingAction() override;
  G4ClassificationOfNewTrack ClassifyNewTrack(const G4Track*) override;

 private:
  RunAction* fRun;
  std::unique_ptr<G4EmCalculator> fCalc;
};

class ActionInitialization : public G4VUserActionInitialization {
 public:
  void BuildForMaster() const override;
  void Build() const override;
};

}  // namespace liga

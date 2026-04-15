#ifndef RunAction_h
#define RunAction_h 1

#include "G4UserRunAction.hh"
#include "globals.hh"
#include "PMMAHit.hh"

class G4Run;

class RunAction : public G4UserRunAction
{
public:
    RunAction();
    virtual ~RunAction();

    virtual void BeginOfRunAction(const G4Run* run);
    virtual void EndOfRunAction(const G4Run* run);

    void FillHistogram(PMMAHitsCollection* hits);
    void FillEventTable(G4double x_mm, G4double y_mm, G4double edep_keV);

private:
    G4String fFileName;
};

#endif
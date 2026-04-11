#ifndef PMMASensitiveDetector_h
#define PMMASensitiveDetector_h 1

#include "G4VSensitiveDetector.hh"
#include "PMMAHit.hh" // будет создан ниже

#pragma once

class G4Step;
class G4HCofThisEvent;

class PMMASensitiveDetector : public G4VSensitiveDetector
{
public:
    PMMASensitiveDetector(const G4String& name);
    virtual ~PMMASensitiveDetector();

    virtual void Initialize(G4HCofThisEvent* hce);
    virtual G4bool ProcessHits(G4Step* step, G4TouchableHistory* history);
    virtual void EndOfEvent(G4HCofThisEvent* hce);

private:
    PMMAHitsCollection* fHitsCollection;
    G4int fHCID;
};

#endif
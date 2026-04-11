#ifndef PMMAHit_h
#define PMMAHit_h 1

#include "G4VHit.hh"
#include "G4THitsCollection.hh"
#include "G4Allocator.hh"
#include "G4ThreeVector.hh"

class PMMAHit : public G4VHit
{
public:
    PMMAHit();
    virtual ~PMMAHit();
    PMMAHit(const PMMAHit& right);
    const PMMAHit& operator=(const PMMAHit& right);
    G4bool operator==(const PMMAHit& right) const;

    inline void* operator new(size_t);
    inline void operator delete(void* aHit);

    virtual void Draw();
    virtual void Print();

    inline void SetPos(G4ThreeVector xyz) { fPos = xyz; }
    inline G4ThreeVector GetPos() const { return fPos; }

    inline void SetEdep(G4double de) { fEdep = de; }
    inline G4double GetEdep() const { return fEdep; }

private:
    G4ThreeVector fPos;
    G4double fEdep;
};

typedef G4THitsCollection<PMMAHit> PMMAHitsCollection;

extern G4ThreadLocal G4Allocator<PMMAHit>* PMMAHitAllocator;

inline void* PMMAHit::operator new(size_t)
{
    if (!PMMAHitAllocator)
        PMMAHitAllocator = new G4Allocator<PMMAHit>;
    return (void*)PMMAHitAllocator->MallocSingle();
}

inline void PMMAHit::operator delete(void* aHit)
{
    PMMAHitAllocator->FreeSingle((PMMAHit*)aHit);
}

#endif
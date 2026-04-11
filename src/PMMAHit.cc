#include "PMMAHit.hh"
#include "G4VVisManager.hh"
#include "G4Circle.hh"
#include "G4Colour.hh"
#include "G4VisAttributes.hh"

G4ThreadLocal G4Allocator<PMMAHit>* PMMAHitAllocator = 0;

PMMAHit::PMMAHit()
    : G4VHit(), fPos(0.,0.,0.), fEdep(0.)
{}

PMMAHit::~PMMAHit()
{}

PMMAHit::PMMAHit(const PMMAHit& right)
    : G4VHit()
{
    fPos = right.fPos;
    fEdep = right.fEdep;
}

const PMMAHit& PMMAHit::operator=(const PMMAHit& right)
{
    if (this != &right) {
        fPos = right.fPos;
        fEdep = right.fEdep;
    }
    return *this;
}

G4bool PMMAHit::operator==(const PMMAHit& right) const
{
    return (this == &right);
}

void PMMAHit::Draw()
{
    // можно добавить визуализацию при желании
}

void PMMAHit::Print()
{
    G4cout << "Hit: position " << fPos << " energy deposit " << fEdep / keV << " keV" << G4endl;
}
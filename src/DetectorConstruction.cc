#include "DetectorConstruction.hh"
#include "G4NistManager.hh"
#include "G4Box.hh"
#include "G4LogicalVolume.hh"
#include "G4PVPlacement.hh"
#include "G4SystemOfUnits.hh"
#include "G4UnitsTable.hh"
#include "G4SDManager.hh"
#include "SensitiveDetector.hh"
#include "G4VisAttributes.hh"
#include "G4Colour.hh"

DetectorConstruction::DetectorConstruction()
{}

DetectorConstruction::~DetectorConstruction()
{}

G4VPhysicalVolume* DetectorConstruction::Construct()
{
    G4NistManager* nist = G4NistManager::Instance();

    G4Material* vacuum = nist->FindOrBuildMaterial("G4_Galactic");
    G4Material* Au = nist->FindOrBuildMaterial("G4_Au");
    G4Material* C = nist->FindOrBuildMaterial("G4_C");

    // PMMA (C5H8O2, density 1.19 g/cm3)
    G4Element* elC = nist->FindOrBuildElement("C");
    G4Element* elH = nist->FindOrBuildElement("H");
    G4Element* elO = nist->FindOrBuildElement("O");
    G4Material* PMMA = new G4Material("PMMA", 1.19 * g/cm3, 3);
    PMMA->AddElement(elC, 5);
    PMMA->AddElement(elH, 8);
    PMMA->AddElement(elO, 2);

    // Geometry matched to the beamline setup:
    // Gold (10 um x 10 um x 25 um), Carbon mask (100 um x 100 um x 475 um),
    // PMMA detector (100 um x 100 um x 1 um) downstream of mask.
    const G4double world_size_xy = 10.0 * mm;
    const G4double world_size_z = 10.0 * mm;
    const G4double au_xy = 10.0 * um;
    const G4double au_thick = 25.0 * um;
    const G4double mask_xy = 100.0 * um;
    const G4double mask_thick = 475.0 * um;
    const G4double pmma_xy = 100.0 * um;
    const G4double pmma_thick = 1.0 * um;
    const G4double gap_gold_to_mask = 12.5 * um;
    const G4double gap_mask_to_pmma = 1.0 * um;

    G4Box* world_solid = new G4Box("World", world_size_xy / 2, world_size_xy / 2, world_size_z / 2);
    G4LogicalVolume* world_log = new G4LogicalVolume(world_solid, vacuum, "World");
    G4VPhysicalVolume* world_phys = new G4PVPlacement(0, G4ThreeVector(), world_log, "World", 0, false, 0);

    const G4double au_z_center = 0.0 * um;
    const G4double mask_z_center =
        au_z_center + au_thick / 2 + gap_gold_to_mask + mask_thick / 2;
    const G4double pmma_z_center =
        mask_z_center + mask_thick / 2 + gap_mask_to_pmma + pmma_thick / 2;

    G4Box* au_solid = new G4Box("Gold", au_xy / 2, au_xy / 2, au_thick / 2);
    G4LogicalVolume* au_log = new G4LogicalVolume(au_solid, Au, "Gold");
    new G4PVPlacement(0, G4ThreeVector(0, 0, au_z_center), au_log, "Gold", world_log, false, 0);

    G4Box* mask_solid = new G4Box("Mask", mask_xy / 2, mask_xy / 2, mask_thick / 2);
    G4LogicalVolume* mask_log = new G4LogicalVolume(mask_solid, C, "Mask");
    new G4PVPlacement(0, G4ThreeVector(0, 0, mask_z_center), mask_log, "Mask", world_log, false, 0);

    G4Box* pmma_solid = new G4Box("PMMA", pmma_xy / 2, pmma_xy / 2, pmma_thick / 2);
    G4LogicalVolume* pmma_log = new G4LogicalVolume(pmma_solid, PMMA, "PMMA");
    new G4PVPlacement(0, G4ThreeVector(0, 0, pmma_z_center), pmma_log, "PMMA", world_log, false, 0);

    G4VisAttributes* goldVisAtt = new G4VisAttributes(G4Colour(1.0, 0.8, 0.0, 0.8));
    au_log->SetVisAttributes(goldVisAtt);

    G4VisAttributes* maskVisAtt = new G4VisAttributes(G4Colour(0.6, 0.3, 0.6, 0.5));
    mask_log->SetVisAttributes(maskVisAtt);

    G4VisAttributes* pmmaVisAtt = new G4VisAttributes(G4Colour(0.3, 0.6, 1.0, 0.7));
    pmma_log->SetVisAttributes(pmmaVisAtt);

    G4VisAttributes* invisibleVisAtt = new G4VisAttributes();
    invisibleVisAtt->SetVisibility(false);
    world_log->SetVisAttributes(invisibleVisAtt);

    return world_phys;
}

void DetectorConstruction::ConstructSDandField()
{
    // Чувствительный детектор создаётся здесь, а не в Construct(), чтобы в
    // многопоточном (MT) режиме у каждого рабочего потока был свой экземпляр SD
    // (Construct() вызывается один раз, геометрия общая; ConstructSDandField() —
    // в каждом потоке).
    PMMASensitiveDetector* pmmaSD = new PMMASensitiveDetector("PMMASD");
    G4SDManager::GetSDMpointer()->AddNewDetector(pmmaSD);
    SetSensitiveDetector("PMMA", pmmaSD);
}
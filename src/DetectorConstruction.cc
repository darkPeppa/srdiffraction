#include "DetectorConstruction.hh"
#include "G4NistManager.hh"
#include "G4Box.hh"
#include "G4LogicalVolume.hh"
#include "G4PVPlacement.hh"
#include "G4SystemOfUnits.hh"
#include "G4UnitsTable.hh"
#include "G4SDManager.hh"
#include "SensitiveDetector.hh"

DetectorConstruction::DetectorConstruction()
{}

DetectorConstruction::~DetectorConstruction()
{}

G4VPhysicalVolume* DetectorConstruction::Construct()
{
    // Получение менеджера материалов NIST
    G4NistManager* nist = G4NistManager::Instance();

    // --- Материалы ---
    // Мир и зазор – вакуум (можно использовать G4_Galactic)
    G4Material* vacuum = nist->FindOrBuildMaterial("G4_Galactic");

    // Титан (NIST)
    G4Material* Ti = nist->FindOrBuildMaterial("G4_Ti");

    // Золото (NIST)
    G4Material* Au = nist->FindOrBuildMaterial("G4_Au");

    // PMMA – сложный материал, создаём вручную (C5H8O2, плотность 1.19 г/см³)
    G4Element* C  = nist->FindOrBuildElement("C");
    G4Element* H  = nist->FindOrBuildElement("H");
    G4Element* O  = nist->FindOrBuildElement("O");
    G4Material* PMMA = new G4Material("PMMA", 1.19 * g/cm3, 3);
    PMMA->AddElement(C, 5);
    PMMA->AddElement(H, 8);
    PMMA->AddElement(O, 2);

    // --- Размеры слоёв (переведём из мкм в мм)---
    // PMMA
    G4double pmma_thick = 1.0 * um;      // 1 мкм
    G4double pmma_xy    = 3000.0 * um;   // 3000 мкм

    // Зазор (пустота)
    G4double gap_thick = 1.0 * um;

    // Титан
    G4double ti_thick = 2.0 * um;
    G4double ti_xy    = 3000.0 * um;

    // Золото
    G4double au_thick = 25.0 * um;
    G4double au_xy    = 10.0 * um;

    // --- Мир (вакуум) – достаточно большой, чтобы вместить всю конструкцию ---
    // Общая высота: PMMA + зазор + Ti + Au = 1+1+2+25 = 29 мкм
    // Сделаем мир 100x100x100 мкм, чтобы был запас
    G4double world_size_xy = 10000.0 * um;   // 1 мм
    G4double world_size_z  = 10000.0 * um;

    G4Box* world_solid = new G4Box("World", world_size_xy/2, world_size_xy/2, world_size_z/2);
    G4LogicalVolume* world_log = new G4LogicalVolume(world_solid, vacuum, "World");
    G4VPhysicalVolume* world_phys = new G4PVPlacement(0, G4ThreeVector(), world_log, "World", 0, false, 0);

    // --- Позиционирование слоёв (все центры смещены так, чтобы нижняя грань PMMA касалась Z = -world_size_z/2)---
    G4double z_bottom = -world_size_z/2;   // нижняя граница мира

    // 1. PMMA
    G4double pmma_z_center = z_bottom + pmma_thick/2;
    G4Box* pmma_solid = new G4Box("PMMA", pmma_xy/2, pmma_xy/2, pmma_thick/2);
    G4LogicalVolume* pmma_log = new G4LogicalVolume(pmma_solid, PMMA, "PMMA");
    new G4PVPlacement(0, G4ThreeVector(0, 0, pmma_z_center), pmma_log, "PMMA", world_log, false, 0);

    G4SDManager* sdManager = G4SDManager::GetSDMpointer();
    PMMASensitiveDetector* pmmaSD = new PMMASensitiveDetector("PMMASD");
    sdManager->AddNewDetector(pmmaSD);
    pmma_log->SetSensitiveDetector(pmmaSD);

    // 2. Зазор (вакуум)
    G4double gap_z_center = pmma_z_center + pmma_thick/2 + gap_thick/2;
    G4Box* gap_solid = new G4Box("Gap", pmma_xy/2, pmma_xy/2, gap_thick/2);
    G4LogicalVolume* gap_log = new G4LogicalVolume(gap_solid, vacuum, "Gap");
    new G4PVPlacement(0, G4ThreeVector(0, 0, gap_z_center), gap_log, "Gap", world_log, false, 0);

    // 3. Титан
    G4double ti_z_center = gap_z_center + gap_thick/2 + ti_thick/2;
    G4Box* ti_solid = new G4Box("Titanium", ti_xy/2, ti_xy/2, ti_thick/2);
    G4LogicalVolume* ti_log = new G4LogicalVolume(ti_solid, Ti, "Titanium");
    new G4PVPlacement(0, G4ThreeVector(0, 0, ti_z_center), ti_log, "Titanium", world_log, false, 0);

    // 4. Золото (маленький слой, по центру по X и Y)
    G4double au_z_center = ti_z_center + ti_thick/2 + au_thick/2;
    G4Box* au_solid = new G4Box("Gold", au_xy/2, au_xy/2, au_thick/2);
    G4LogicalVolume* au_log = new G4LogicalVolume(au_solid, Au, "Gold");
    new G4PVPlacement(0, G4ThreeVector(0, 0, au_z_center), au_log, "Gold", world_log, false, 0);

    return world_phys;
}
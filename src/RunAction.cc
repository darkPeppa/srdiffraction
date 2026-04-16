#include "RunAction.hh"
#include "PMMAHit.hh"
#include "G4Run.hh"
#include "G4AnalysisManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4UnitsTable.hh"

RunAction::RunAction()
    : G4UserRunAction(), fFileName("energy_deposition_pmma.csv")
{}

RunAction::~RunAction()
{}

void RunAction::BeginOfRunAction(const G4Run*)
{
    // Создаём менеджер анализа
    G4AnalysisManager* analysisManager = G4AnalysisManager::Instance();
    analysisManager->Reset();
    analysisManager->SetDefaultFileType("csv");
    analysisManager->SetFileName(fFileName);
    analysisManager->OpenFile();
    analysisManager->SetVerboseLevel(1);
    analysisManager->SetFirstHistoId(1);

    // Карта энерговыделения в PMMA с повышенным разрешением в центре.
    // Окно 200x200 мкм и 200 бинов -> 1 мкм/бин (10 мкм золото ~10 бинов).
    G4int nbins = 200;
    G4double xmin = -100.0 * um;
    G4double xmax =  100.0 * um;
    G4double ymin = -100.0 * um;
    G4double ymax =  100.0 * um;

    analysisManager->CreateH2("Edep_2D", "Energy deposition in PMMA (keV)", nbins, xmin, xmax, nbins, ymin, ymax);
    analysisManager->SetH2XAxisTitle(1, "X position [mm]");
    analysisManager->SetH2YAxisTitle(1, "Y position [mm]");
    analysisManager->SetH2ZAxisTitle(1, "Deposited energy [keV]");
    analysisManager->CreateH2("EntryCount_2D", "Entry count in PMMA", nbins, xmin, xmax, nbins, ymin, ymax);
    analysisManager->SetH2XAxisTitle(2, "X position [mm]");
    analysisManager->SetH2YAxisTitle(2, "Y position [mm]");
    analysisManager->SetH2ZAxisTitle(2, "Entries");

    // Beamline-like table: one row per PMMA entry (x,y,z,edep).
    analysisManager->CreateNtuple("Edep_table", "Per-entry PMMA table");
    analysisManager->CreateNtupleDColumn("x");
    analysisManager->CreateNtupleDColumn("y");
    analysisManager->CreateNtupleDColumn("z");
    analysisManager->CreateNtupleDColumn("Edep");
    analysisManager->FinishNtuple();
}

void RunAction::FillHistogram(PMMAHitsCollection* hits)
{
    G4AnalysisManager* analysisManager = G4AnalysisManager::Instance();
    G4int n_hit = hits->GetSize();
    for (G4int i=0; i<n_hit; ++i) {
        PMMAHit* hit = (*hits)[i];
        G4ThreeVector pos = hit->GetPos();
        G4double edep = hit->GetEdep() / keV;
        analysisManager->FillH2(1, pos.x(), pos.y(), edep);
        analysisManager->FillH2(2, pos.x(), pos.y(), 1.0);
    }
}

void RunAction::FillEventTable(G4double x_mm, G4double y_mm, G4double z_mm, G4double edep_keV)
{
    G4AnalysisManager* analysisManager = G4AnalysisManager::Instance();
    analysisManager->FillNtupleDColumn(0, x_mm);
    analysisManager->FillNtupleDColumn(1, y_mm);
    analysisManager->FillNtupleDColumn(2, z_mm);
    analysisManager->FillNtupleDColumn(3, edep_keV);
    analysisManager->AddNtupleRow();
}

void RunAction::EndOfRunAction(const G4Run*)
{
    G4AnalysisManager* analysisManager = G4AnalysisManager::Instance();
    analysisManager->Write();
    analysisManager->CloseFile(false);

    G4cout << "\n======= Run completed. Results saved in " << fFileName << " =======" << G4endl;
}
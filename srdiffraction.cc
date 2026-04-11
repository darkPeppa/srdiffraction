#include "DetectorConstruction.hh"
#include "PhysicsList.hh"
#include "ActionInitialization.hh"

#include "G4RunManager.hh"
#include "G4UImanager.hh"
#include "G4VisExecutive.hh"
#include "G4UIExecutive.hh"

int main(int argc, char** argv)
{
    // Менеджер запуска
    G4RunManager* runManager = new G4RunManager();

    // Геометрия
    runManager->SetUserInitialization(new DetectorConstruction());

    // Физический список (Livermore для низких энергий)
    runManager->SetUserInitialization(new PhysicsList());

    // Действия пользователя (первичный генератор, run action, event action)
    runManager->SetUserInitialization(new ActionInitialization());

    // Инициализация
    runManager->Initialize();

    // Визуализация
    G4VisManager* visManager = new G4VisExecutive();
    visManager->Initialize();

    G4UImanager* UImanager = G4UImanager::GetUIpointer();

    if (argc == 1)   // Интерактивный режим
    {
        G4UIExecutive* ui = new G4UIExecutive(argc, argv);
        UImanager->ApplyCommand("/control/execute vis.mac");
        ui->SessionStart();
        delete ui;
    }
    else             // Пакетный режим (запуск с макросом)
    {
        G4String command = "/control/execute ";
        command += argv[1];
        UImanager->ApplyCommand(command);
    }

    delete visManager;
    delete runManager;
    return 0;
}
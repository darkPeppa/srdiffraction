#include "DetectorConstruction.hh"
#include "PhysicsList.hh"
#include "ActionInitialization.hh"

#include "G4RunManagerFactory.hh"
#include "G4Threading.hh"
#include "G4UImanager.hh"
#include "G4VisExecutive.hh"
#include "G4UIExecutive.hh"

#include <cstdlib>

int main(int argc, char** argv)
{
    // Менеджер запуска.
    // Используем фабрику: в интерактивном режиме (с визуализацией) — последовательный
    // менеджер, в пакетном режиме — многопоточный (MT) для ускорения расчёта.
    const G4bool interactive = (argc == 1);
    G4RunManager* runManager = G4RunManagerFactory::CreateRunManager(
        interactive ? G4RunManagerType::Serial : G4RunManagerType::Default);

    // Число рабочих потоков в MT-режиме.
    // По умолчанию — по числу ядер; можно переопределить переменной окружения
    // SRD_NTHREADS (например, SRD_NTHREADS=4) или штатной G4FORCENUMBEROFTHREADS.
    if (!interactive) {
        G4int nThreads = G4Threading::G4GetNumberOfCores();
        if (const char* env = std::getenv("SRD_NTHREADS")) {
            const G4int requested = std::atoi(env);
            if (requested > 0) nThreads = requested;
        }
        runManager->SetNumberOfThreads(nThreads);
        G4cout << "=== MT mode: " << nThreads << " worker threads ===" << G4endl;
    }

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
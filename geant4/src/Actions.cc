#include "Actions.hh"

#include "Config.hh"
#include "DetectorConstruction.hh"
#include "H5Out.hh"
#include "PrimaryGeneratorAction.hh"
#include "TrackInfo.hh"

#include <G4AutoLock.hh>
#include <G4BiasingProcessInterface.hh>
#include <G4EmCalculator.hh>
#include <G4Electron.hh>
#include <G4Event.hh>
#include <G4EventManager.hh>
#include <G4Gamma.hh>
#include <G4LogicalVolume.hh>
#include <G4Positron.hh>
#include <G4RunManager.hh>
#include <G4PrimaryParticle.hh>
#include <G4Run.hh>
#include <G4Step.hh>
#include <G4SystemOfUnits.hh>
#include <G4Threading.hh>
#include <G4Track.hh>
#include <G4VProcess.hh>
#include <Randomize.hh>

#include <atomic>
#include <cstdlib>
#include <cmath>
#include <fstream>
#include <iomanip>

namespace liga {

namespace {
G4Mutex gMergeMutex = G4MUTEX_INITIALIZER;
ThreadData* gMasterData = nullptr;
std::atomic<long long> gEventsDone{0};
std::chrono::steady_clock::time_point gRunStart;
}  // namespace

// =================================================================== RunAction
RunAction::RunAction(bool master) : fMaster(master) {}
RunAction::~RunAction() = default;

void RunAction::BeginOfRunAction(const G4Run*) {
  const Config& c = Cfg();
  fData = std::make_unique<ThreadData>(c);
  fStart = std::chrono::steady_clock::now();
  if (fMaster) {
    G4AutoLock l(&gMergeMutex);
    gMasterData = fData.get();
    gEventsDone = 0;
    gRunStart = fStart;
  } else if (c.scoring.phase_space_out) {
    const std::string f = c.scoring.phase_space_file + "_t" + std::to_string(G4Threading::G4GetThreadId()) + ".bin";
    fData->psOut = std::make_unique<std::ofstream>(f, std::ios::binary | std::ios::trunc);
    if (!*fData->psOut) G4Exception("RunAction", "PS001", FatalException, ("cannot open " + f).c_str());
  }
}

void RunAction::EndOfRunAction(const G4Run* run) {
  if (!fMaster) {
    if (!fData->primDump.empty()) {
      const std::string f = Cfg().run.output + "_t" + std::to_string(G4Threading::G4GetThreadId()) + ".csv";
      std::ofstream o(f);
      o << "e_keV,x_mm,y_mm,z_mm,ux,uy,uz,px,py,pz,w\n";
      o.precision(10);
      for (const auto& r : fData->primDump) {
        for (size_t i = 0; i < r.size(); ++i) o << (i ? "," : "") << r[i];
        o << "\n";
      }
    }
    fData->FlushPS();
    if (fData->psOut) fData->psOut->close();
    G4AutoLock l(&gMergeMutex);
    if (gMasterData) gMasterData->Merge(*fData);
    return;
  }
  const double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - fStart).count();
  const Config& c = Cfg();
  if (run->GetNumberOfEvent() > 0 && !c.run.output.empty() && c.run.mode == "transport") {
    WriteHDF5(c.run.output, c, *fData, run->GetNumberOfEvent(), secs);
    G4cout << "[liga] wrote " << c.run.output << "  events=" << run->GetNumberOfEvent() << "  wall=" << secs << " s"
           << G4endl;
  }
  G4AutoLock l(&gMergeMutex);
  gMasterData = nullptr;
}

// ================================================================= EventAction
void EventAction::EndOfEventAction(const G4Event*) {
  fRun->Data()->EndEvent();
  const long long every = Cfg().run.progress_every;
  const long long n = ++gEventsDone;
  if (every > 0 && n % every == 0) {
    const double el = std::chrono::duration<double>(std::chrono::steady_clock::now() - gRunStart).count();
    const double tot = double(Cfg().run.n_events);
    G4cout << "[liga] " << n << " / " << (long long)tot << " events, " << std::fixed << std::setprecision(1) << el
           << " s elapsed, ETA " << el / n * (tot - n) << " s" << G4endl;
  }
}

// ============================================================== TrackingAction
void TrackingAction::PreUserTrackingAction(const G4Track* t) {
  if (t->GetUserInformation()) return;
  auto* info = new TrackInfo();
  if (t->GetParentID() == 0) {
    const G4PrimaryParticle* pp = t->GetDynamicParticle()->GetPrimaryParticle();
    const auto* pi = pp ? dynamic_cast<const PrimaryInfo*>(pp->GetUserInformation()) : nullptr;
    double w = t->GetWeight();
    if (pi) {
      info->flags = pi->flags;
      info->primaryEnergy = pi->energy;
      info->yLab = pi->yLab;
      if (std::abs(w - pi->weight) > 1e-12 * std::max(1.0, pi->weight)) {
        const_cast<G4Track*>(t)->SetWeight(pi->weight);
        w = pi->weight;
      }
    } else {
      info->primaryEnergy = t->GetKineticEnergy();
    }
    // Учёт первичных: баланс энергии и сумма весов.
    {
      ThreadData* d = fRun->Data();
      d->eIncident += t->GetKineticEnergy() * w;
      d->sumW += w;
      d->sumW2 += w * w;
      if (Cfg().scoring.slab_test) ++d->slabPrimaries;
    }
  }
  const_cast<G4Track*>(t)->SetUserInformation(info);
}

// ============================================================== SteppingAction
SteppingAction::SteppingAction(RunAction* r) : fRun(r) {
  if (const auto* p = DetectorConstruction::PMMALayer()) {
    fHavePMMA = true;
    fPMMAFront = p->z_front;
    fPMMABack = p->z_back;
  }
  const Config& c = Cfg();
  if (c.scoring.slab_test) {
    for (const auto& l : DetectorConstruction::Layers())
      if (l.name == c.scoring.slab_layer) {
        fSlab = true;
        fSlabFront = l.z_front;
        fSlabBack = l.z_back;
      }
    if (!fSlab) G4Exception("SteppingAction", "SLAB01", FatalException, "slab_layer not found");
  }
  fPlane = c.scoring.phase_space_out;
  fPlaneZ = c.scoring.phase_space_plane_z_mm * mm;
}

void SteppingAction::UserSteppingAction(const G4Step* step) {
  G4Track* track = step->GetTrack();
  auto* info = static_cast<TrackInfo*>(track->GetUserInformation());
  const G4StepPoint* pre = step->GetPreStepPoint();
  const G4StepPoint* post = step->GetPostStepPoint();
  const G4LogicalVolume* preLV = pre->GetTouchableHandle()->GetVolume()->GetLogicalVolume();
  const Role role = DetectorConstruction::RoleOf(preLV);
  const double w = track->GetWeight();
  ThreadData* d = fRun->Data();
  const bool isGamma = track->GetDefinition() == G4Gamma::Definition();

  // 1) Метки рассеяния фотонов (процесс, завершивший шаг, произошёл в объёме pre-точки).
  if (isGamma) {
    if (const G4VProcess* proc = post->GetProcessDefinedStep()) {
      // При смещении процессы обёрнуты: имя вида "biasWrapper(compt)" — ищем подстроку.
      const G4String& pn = proc->GetProcessName();
      int ptype = -1;
      if (pn.find("Rayl") != std::string::npos) { info->flags |= RaylBit(role); ptype = 0; }
      else if (pn.find("compt") != std::string::npos) { info->flags |= ComptBit(role); ptype = 1; }
      else if (pn.find("phot") != std::string::npos) ptype = 2;
      else if (pn.find("conv") != std::string::npos) ptype = 3;
      if (ptype >= 0) {
        if (info->nInteractions == 0) {
          info->firstProcess = ptype;
          if (fSlab && track->GetParentID() == 0 && preLV->GetName().rfind(Cfg().scoring.slab_layer, 0) == 0)
            ++d->slabFirst[ptype];
        }
        ++info->nInteractions;
      }
    }
  }

  // 2) Вторичные частицы наследуют метки и получают бит происхождения.
  if (const auto* secs = step->GetSecondaryInCurrentStep()) {
    for (const G4Track* s : *secs) {
      auto* ci = new TrackInfo();
      // Клон фотона, созданный операцией смещения (принудительное взаимодействие), — это
      // тот же фотон, а не продукт взаимодействия: наследует метки без бита происхождения.
      const auto* bpi = dynamic_cast<const G4BiasingProcessInterface*>(s->GetCreatorProcess());
      const bool clone = bpi && bpi->GetWrappedProcess() == nullptr;  // не-физическая операция смещения
      ci->flags = clone ? info->flags : (info->flags | OriginBit(role));
      if (clone) ci->nInteractions = info->nInteractions;
      ci->primaryEnergy = info->primaryEnergy;
      ci->yLab = info->yLab;
      ci->birthRole = role;
      const_cast<G4Track*>(s)->SetUserInformation(ci);
    }
  }

  // 3) Энерговыделение.
  const double edep = step->GetTotalEnergyDeposit();
  if (edep > 0) {
    const double ew = edep * w;
    d->eDepByRole[int(role)] += ew;
    if (role == Role::PMMA && fHavePMMA) {
      const G4ThreeVector p = pre->GetPosition() + G4UniformRand() * (post->GetPosition() - pre->GetPosition());
      const double zrel = p.z() - fPMMAFront;
      for (auto& g : d->grids) {
        const long idx = g->Locate(p.x(), p.y(), zrel);
        if (idx >= 0) g->Add(idx, ew, info->flags);
      }
      const int reg = d->RegionOf(p.x(), p.y());
      d->regionEdep[size_t(reg) * kNCategories + Classify(info->flags)] += ew;
      const int eb = d->EBin(info->primaryEnergy / keV);
      if (eb >= 0) {
        d->edepByPrimE[size_t(reg) * d->nE + eb] += ew;
        if (HasFeature(info->flags, kF_MembraneAnyScatter)) d->edepByPrimEMem[size_t(reg) * d->nE + eb] += ew;
      }
    }
  }

  // 4) Спектр фотонов, входящих в ПММА.
  if (isGamma && fHavePMMA && post->GetStepStatus() == fGeomBoundary && role != Role::PMMA) {
    if (const auto* postPV = post->GetTouchableHandle()->GetVolume()) {
      if (DetectorConstruction::RoleOf(postPV->GetLogicalVolume()) == Role::PMMA) {
        const double e = post->GetKineticEnergy();
        const int eb = d->EBin(e / keV);
        if (eb >= 0) {
          const int reg = d->RegionOf(post->GetPosition().x(), post->GetPosition().y());
          const int cls = HasFeature(info->flags, kF_MembraneAnyScatter) ? 1 : (Classify(info->flags) == kDirect ? 0 : 2);
          const size_t k = (size_t(reg) * ThreadData::kNEntryClasses + cls) * d->nE + eb;
          d->entrySpec[k] += w;
          d->entryEnergy[k] += e * w;
        }
      }
    }
  }

  // 5) Плоскость фазового пространства (этап 1): записываем фотоны и прекращаем трек.
  //    Проверяется ДО учёта выхода из мира: фотон может пересечь плоскость и
  //    границу мира за один шаг.
  bool atPlane = false;
  if (fPlane && pre->GetPosition().z() < fPlaneZ && post->GetPosition().z() >= fPlaneZ) {
    atPlane = true;
    if (isGamma) {
      const G4ThreeVector a = pre->GetPosition(), b = post->GetPosition();
      const double t = (fPlaneZ - a.z()) / (b.z() - a.z());
      const G4ThreeVector p = a + t * (b - a);
      const SourceSpec& s = Cfg().source;
      const double dx = p.x() / mm, dy = p.y() / mm;  // старт этапа 1 — в точке (0,0)
      double wf = (std::abs(dx) <= s.beam_half_x_mm) ? 1.0 : 0.0;
      if (s.scan_mode != "none" && std::abs(info->yLab + dy) > s.scan_half_amplitude_mm) wf = 0.0;
      const G4ThreeVector u = pre->GetMomentumDirection();
      const G4ThreeVector pol = pre->GetPolarization();
      PSRecord r{pre->GetKineticEnergy() / keV, dx, dy, dx, dy, u.x(), u.y(), u.z(), pol.x(), pol.y(), pol.z(),
                 w * wf, info->yLab, info->flags, 22, G4EventManager::GetEventManager()->GetConstCurrentEvent()->GetEventID()};
      d->psBuffer.push_back(r);
      ++d->psCount;
      d->psSumW += w * wf;
    }
    d->eKilledPlane += post->GetKineticEnergy() * w;
    track->SetTrackStatus(fStopAndKill);
  }

  // 6) Выход за пределы мира.
  if (!atPlane && post->GetStepStatus() == fWorldBoundary) d->eEscape += post->GetKineticEnergy() * w;

  // 7) Тест пластины: первичный фотон прошёл заднюю грань без единого взаимодействия.
  if (fSlab && isGamma && track->GetParentID() == 0 && info->nInteractions == 0 &&
      preLV->GetName().rfind(Cfg().scoring.slab_layer, 0) == 0 && post->GetStepStatus() == fGeomBoundary &&
      post->GetPosition().z() >= fSlabBack - 1e-9 * mm)
    ++d->slabUnscattered;
}

// ============================================================== StackingAction
StackingAction::StackingAction(RunAction* r) : fRun(r), fCalc(std::make_unique<G4EmCalculator>()) {}
StackingAction::~StackingAction() = default;

G4ClassificationOfNewTrack StackingAction::ClassifyNewTrack(const G4Track* t) {
  if (Cfg().run.mode == "dump_primaries" && t->GetParentID() == 0) {
    // Контроль генератора: записываем первичные частицы без транспорта.
    const auto p = t->GetPosition() / mm;
    const auto u = t->GetMomentumDirection();
    const auto q = t->GetPolarization();
    double w = t->GetWeight();
    const G4PrimaryParticle* pp = t->GetDynamicParticle()->GetPrimaryParticle();
    if (pp) w = pp->GetWeight();
    fRun->Data()->primDump.push_back({t->GetKineticEnergy() / keV, p.x(), p.y(), p.z(), u.x(), u.y(), u.z(), q.x(), q.y(),
                                      q.z(), w});
    return fKill;
  }
  if (!(t->GetWeight() > 0)) return fKill;
  const PhysicsSpec& p = Cfg().physics;
  if (!p.kill_unreachable_electrons || t->GetParentID() == 0) return fUrgent;
  const auto* def = t->GetDefinition();
  if (def != G4Electron::Definition() && def != G4Positron::Definition()) return fUrgent;
  const double e = t->GetKineticEnergy();
  const double z = t->GetPosition().z();
  const LayerGeom* pm = DetectorConstruction::PMMALayer();
  double dist = 0;
  const G4Material* m = nullptr;
  if (!pm) {
    dist = 1e30;
  } else if (z < pm->z_front) {
    dist = pm->z_front - z;
    m = DetectorConstruction::LeastDenseMaterialBetween(z, pm->z_front);
  } else if (z > pm->z_back) {
    dist = z - pm->z_back;
    m = DetectorConstruction::LeastDenseMaterialBetween(pm->z_back, z);
  }
  if (dist <= 0) return fUrgent;
  double range = 0;
  if (m) {
    range = fCalc->GetCSDARange(e, G4Electron::Definition(), m);
    if (!(range > 0)) range = fCalc->GetRange(e, G4Electron::Definition(), m);
    if (!(range > 0)) return fUrgent;  // не удалось оценить — не рискуем
  }
  if (!m || 1.2 * range < dist) {
    fRun->Data()->eKilledStack += e * t->GetWeight();
    return fKill;
  }
  return fUrgent;
}

// ======================================================= ActionInitialization
void ActionInitialization::BuildForMaster() const { SetUserAction(new RunAction(true)); }

void ActionInitialization::Build() const {
  auto* r = new RunAction(false);
  SetUserAction(r);
  SetUserAction(new PrimaryGeneratorAction());
  SetUserAction(new EventAction(r));
  SetUserAction(new TrackingAction(r));
  SetUserAction(new SteppingAction(r));
  SetUserAction(new StackingAction(r));
}

}  // namespace liga

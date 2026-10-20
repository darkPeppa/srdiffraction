#include "PrimaryGeneratorAction.hh"

#include "Config.hh"
#include "Scoring.hh"
#include "TrackInfo.hh"

#include <G4AutoLock.hh>
#include <G4Event.hh>
#include <G4Gamma.hh>
#include <G4GeneralParticleSource.hh>
#include <G4PrimaryParticle.hh>
#include <G4PrimaryVertex.hh>
#include <G4SystemOfUnits.hh>
#include <Randomize.hh>

#include <algorithm>
#include <cmath>
#include <fstream>
#include <map>
#include <sstream>
#include <stdexcept>

namespace liga {

namespace {
G4Mutex gLoadMutex = G4MUTEX_INITIALIZER;
std::map<std::string, std::shared_ptr<const SRTable>> gTables;
std::map<std::string, std::shared_ptr<const PhaseSpace>> gPS;

size_t SampleCdf(const std::vector<double>& cdf, double u) {
  const double t = u * cdf.back();
  size_t i = size_t(std::upper_bound(cdf.begin(), cdf.end(), t) - cdf.begin());
  return std::min(i, cdf.size() - 1);
}
}  // namespace

// ------------------------------------------------------------------ SRTable
std::shared_ptr<const SRTable> SRTable::Load(const std::string& path) {
  G4AutoLock lock(&gLoadMutex);
  if (auto it = gTables.find(path); it != gTables.end()) return it->second;
  std::ifstream in(path);
  if (!in) throw std::runtime_error("cannot open source table " + path);
  auto t = std::make_shared<SRTable>();
  std::string line;
  bool header = false;
  std::vector<double> ws, wp;
  while (std::getline(in, line)) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    if (line.empty() || line[0] == '#') continue;
    if (!header) { header = true; continue; }  // строка с именами колонок
    std::stringstream ss(line);
    std::string tok;
    std::vector<double> v;
    while (std::getline(ss, tok, ',')) v.push_back(std::stod(tok));
    if (v.size() < 6) throw std::runtime_error("bad row in " + path + ": " + line);
    if (v[1] <= v[0] || v[3] < v[2] || v[4] < 0 || v[5] < 0) throw std::runtime_error("invalid row in " + path);
    t->eLo.push_back(v[0]); t->eHi.push_back(v[1]); t->psiLo.push_back(v[2]); t->psiHi.push_back(v[3]);
    ws.push_back(v[4]); wp.push_back(v[5]);
  }
  const size_t n = ws.size();
  if (!n) throw std::runtime_error("empty source table " + path);
  t->cdf.resize(2 * n);
  double acc = 0;
  for (size_t i = 0; i < n; ++i) {
    acc += ws[i]; t->cdf[2 * i] = acc;
    acc += wp[i]; t->cdf[2 * i + 1] = acc;
  }
  t->totalWeight = acc;
  if (acc <= 0) throw std::runtime_error("source table has zero total weight");
  // Колонки по psi
  std::vector<double> edges;
  for (size_t i = 0; i < n; ++i) { edges.push_back(t->psiLo[i]); edges.push_back(t->psiHi[i]); }
  std::sort(edges.begin(), edges.end());
  edges.erase(std::unique(edges.begin(), edges.end(), [](double a, double b) { return std::abs(a - b) < 1e-12; }), edges.end());
  t->psiEdges = edges;
  t->colRows.assign(edges.size() > 1 ? edges.size() - 1 : 1, {});
  for (size_t i = 0; i < n; ++i) {
    int k = int(std::upper_bound(edges.begin(), edges.end(), t->psiLo[i] + 1e-12) - edges.begin()) - 1;
    k = std::clamp(k, 0, int(t->colRows.size()) - 1);
    t->colRows[k].push_back(int(i));
  }
  t->colCdf.resize(t->colRows.size());
  for (size_t k = 0; k < t->colRows.size(); ++k) {
    double a = 0;
    for (int r : t->colRows[k]) { a += ws[r]; t->colCdf[k].push_back(a); a += wp[r]; t->colCdf[k].push_back(a); }
  }
  gTables[path] = t;
  return t;
}

// --------------------------------------------------------------- PhaseSpace
std::shared_ptr<const PhaseSpace> PhaseSpace::Load(const std::string& files) {
  G4AutoLock lock(&gLoadMutex);
  if (auto it = gPS.find(files); it != gPS.end()) return it->second;
  auto ps = std::make_shared<PhaseSpace>();
  std::stringstream ss(files);
  std::string f;
  while (std::getline(ss, f, ';')) {
    if (f.empty()) continue;
    std::ifstream in(f, std::ios::binary);
    if (!in) throw std::runtime_error("cannot open phase space " + f);
    in.seekg(0, std::ios::end);
    const auto bytes = in.tellg();
    in.seekg(0);
    if (bytes % sizeof(PSRecord)) throw std::runtime_error("corrupt phase space (size) " + f);
    const size_t n = size_t(bytes) / sizeof(PSRecord);
    const size_t old = ps->rec.size();
    ps->rec.resize(old + n);
    in.read(reinterpret_cast<char*>(ps->rec.data() + old), std::streamsize(n * sizeof(PSRecord)));
  }
  // Отбрасываем записи нулевого веса и не-фотоны (этап 1 пишет только фотоны).
  ps->rec.erase(std::remove_if(ps->rec.begin(), ps->rec.end(), [](const PSRecord& r) { return !(r.w > 0) || r.pdg != 22; }),
                ps->rec.end());
  if (ps->rec.empty()) throw std::runtime_error("phase space is empty: " + files);
  ps->cdf.resize(ps->rec.size());
  double a = 0;
  for (size_t i = 0; i < ps->rec.size(); ++i) { a += ps->rec[i].w; ps->cdf[i] = a; }
  ps->sumW = a;
  gPS[files] = ps;
  return ps;
}

// ------------------------------------------------------ PrimaryGeneratorAction
PrimaryGeneratorAction::PrimaryGeneratorAction() {
  const SourceSpec& s = Cfg().source;
  fGamma = G4Gamma::Definition();
  if (s.mode == "gps") {
    fGPS = std::make_unique<G4GeneralParticleSource>();
  } else if (s.mode == "sr_table") {
    fTable = SRTable::Load(s.table_file);
  } else if (s.mode == "phase_space") {
    fPS = PhaseSpace::Load(s.phase_space_files);
    if (s.ps_n_primaries <= 0) throw std::runtime_error("source.ps_n_primaries must be > 0 for phase_space mode");
  } else if (s.mode != "pencil") {
    throw std::runtime_error("unknown source.mode " + s.mode);
  }
}

PrimaryGeneratorAction::~PrimaryGeneratorAction() = default;

double PrimaryGeneratorAction::SampleWindow(double& x, double& y) const {
  const SourceSpec& s = Cfg().source;
  const double Wx = s.window_half_x_mm, Wy = s.window_half_y_mm;
  const double Cx = std::min(s.core_half_x_mm, Wx), Cy = std::min(s.core_half_y_mm, Wy);
  const bool useCore = s.core_fraction > 0 && Cx > 0 && Cy > 0;
  if (useCore && G4UniformRand() < s.core_fraction) {
    x = (2 * G4UniformRand() - 1) * Cx;
    y = (2 * G4UniformRand() - 1) * Cy;
  } else {
    x = (2 * G4UniformRand() - 1) * Wx;
    y = (2 * G4UniformRand() - 1) * Wy;
  }
  if (!useCore) return 1.0;
  // Вес = (равномерная плотность по окну) / (смешанная плотность выборки).
  const double aWin = 4 * Wx * Wy, aCore = 4 * Cx * Cy;
  const bool inCore = std::abs(x) <= Cx && std::abs(y) <= Cy;
  const double p = (inCore ? s.core_fraction / aCore : 0.0) + (1 - s.core_fraction) / aWin;
  return (1.0 / aWin) / p;
}

void PrimaryGeneratorAction::Emit(G4Event* ev, double e, const G4ThreeVector& pos, const G4ThreeVector& dir,
                                  const G4ThreeVector& pol, double w, Flags flags, double yLab) {
  auto* v = new G4PrimaryVertex(pos, 0.0);
  auto* p = new G4PrimaryParticle(fGamma);
  p->SetKineticEnergy(e);
  p->SetMomentumDirection(dir);
  if (pol.mag2() > 0) p->SetPolarization(pol);
  p->SetWeight(w);
  p->SetUserInformation(new PrimaryInfo(flags, e, yLab, w));
  v->SetPrimary(p);
  ev->AddPrimaryVertex(v);
}

static G4ThreeVector Transverse(const G4ThreeVector& e, const G4ThreeVector& d) {
  G4ThreeVector p = e - (e.dot(d)) * d;
  return p.mag2() > 0 ? p.unit() : G4ThreeVector();
}

void PrimaryGeneratorAction::GeneratePrimaries(G4Event* ev) {
  const SourceSpec& s = Cfg().source;
  const double z = s.z_mm * mm;

  if (fGPS) {
    fGPS->GeneratePrimaryVertex(ev);
    return;
  }
  if (s.mode == "pencil") {
    Emit(ev, s.pencil_energy_keV * keV, {0, 0, z}, {0, 0, 1}, {1, 0, 0}, 1.0, 0, 0.0);
    return;
  }

  double x = 0, y = 0;
  if (fPS) {
    const auto& r = fPS->rec[SampleCdf(fPS->cdf, G4UniformRand())];
    const double wImp = SampleWindow(x, y);
    const double w = (fPS->sumW / s.ps_n_primaries) * wImp;
    G4ThreeVector d(r.ux, r.uy, r.uz), pol(r.px, r.py, r.pz);
    Emit(ev, r.e_keV * keV, {x * mm, y * mm, z}, d.unit(), pol, w, r.flags, r.ylab_mm);
    return;
  }

  // ---------------- sr_table (режим B)
  const double L = s.distance_m * 1000.0;  // мм
  const double xs = s.source_sigma_x_mm > 0 ? G4RandGauss::shoot(0, s.source_sigma_x_mm) : 0;
  const double ys = s.source_sigma_y_mm > 0 ? G4RandGauss::shoot(0, s.source_sigma_y_mm) : 0;
  const double ay = s.electron_divergence_sigma_mrad > 0 ? G4RandGauss::shoot(0, s.electron_divergence_sigma_mrad) * 1e-3 : 0;

  size_t row;
  bool isPi;
  double psiRel;  // рад, угол излучения относительно направления электрона
  double wScan = 1.0;
  if (s.scan_mode == "none") {
    // Неподвижный образец: точка видит только угол psi = (Y_hole - ys)/L - ay.
    const double target = ((s.hole_offset_y_mm - ys) / L - ay) * 1e3;  // мрад
    const auto& e = fTable->psiEdges;
    if (target < e.front() || target >= e.back()) {
      Emit(ev, 1 * keV, {0, 0, z}, {0, 0, 1}, {}, 0.0, 0, 0.0);  // вне таблицы — пустая история
      return;
    }
    const int k = int(std::upper_bound(e.begin(), e.end(), target) - e.begin()) - 1;
    const auto& col = fTable->colCdf[k];
    if (col.empty() || col.back() <= 0) {
      Emit(ev, 1 * keV, {0, 0, z}, {0, 0, 1}, {}, 0.0, 0, 0.0);
      return;
    }
    const size_t j = SampleCdf(col, G4UniformRand());
    row = size_t(fTable->colRows[k][j / 2]);
    isPi = j % 2;
    psiRel = target * 1e-3;
  } else {
    const size_t j = SampleCdf(fTable->cdf, G4UniformRand());
    row = j / 2;
    isPi = j % 2;
    psiRel = (fTable->psiLo[row] + G4UniformRand() * (fTable->psiHi[row] - fTable->psiLo[row])) * 1e-3;
  }
  const double e = (fTable->eLo[row] + G4UniformRand() * (fTable->eHi[row] - fTable->eLo[row])) * keV;
  const double psiLab = psiRel + ay;
  const double yLab = ys + L * psiLab;  // вертикальная координата в плоскости генерации (лаб. СК), мм

  double wImp = 1.0;
  if (s.scan_mode == "explicit" && s.window_half_y_mm > 0) {
    // Явное сканирование: случайное положение сборки s∈[-A,A]; фотон попадает
    // в окно только если |yLab - (s + y_hole)| <= Wy. Вес A/Wy сохраняет
    // нормировку, совпадающую с усреднённым режимом.
    const double A = s.scan_half_amplitude_mm, Wy = s.window_half_y_mm;
    const double sc = (2 * G4UniformRand() - 1) * A;
    x = (2 * G4UniformRand() - 1) * s.window_half_x_mm;
    y = yLab - (sc + s.hole_offset_y_mm);
    wScan = (std::abs(y) <= Wy) ? A / Wy : 0.0;
  } else {
    wImp = SampleWindow(x, y);
  }
  const double thx = (x + s.hole_offset_x_mm - xs) / L;
  const G4ThreeVector dir = G4ThreeVector(thx, psiLab, 1.0).unit();
  G4ThreeVector pol;
  if (s.polarization) pol = Transverse(isPi ? G4ThreeVector(0, 1, 0) : G4ThreeVector(1, 0, 0), dir);
  Emit(ev, e, {x * mm, y * mm, z}, dir, pol, wImp * wScan, 0, yLab);
}

}  // namespace liga

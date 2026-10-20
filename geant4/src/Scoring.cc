#include "Scoring.hh"

#include <G4SystemOfUnits.hh>

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace liga {

// ---------------------------------------------------------------- VoxelScorer
VoxelScorer::VoxelScorer(const GridSpec& g) : fSpec(g) {
  auto conv = [](const std::vector<double>& e, const char* ax) {
    if (e.size() < 2) throw std::runtime_error(std::string("grid needs >=2 edges along ") + ax);
    std::vector<double> o(e.size());
    for (size_t i = 0; i < e.size(); ++i) {
      o[i] = e[i] * um;
      if (i && o[i] <= o[i - 1]) throw std::runtime_error(std::string("grid edges not increasing along ") + ax);
    }
    return o;
  };
  fX = conv(g.x_edges_um, "x");
  fY = conv(g.y_edges_um, "y");
  fZ = conv(g.z_edges_um, "z");
  fNx = int(fX.size()) - 1;
  fNy = int(fY.size()) - 1;
  fNz = int(fZ.size()) - 1;
  fN = long(fNx) * fNy * fNz;
  total.assign(fN, 0.0);
  total_sq.assign(fN, 0.0);
  if (g.categories) {
    cat.assign(size_t(kNCategories) * fN, 0.0);
    feat.assign(size_t(kNFeatures) * fN, 0.0);
    mem_sq.assign(fN, 0.0);
    fEvtMem.assign(fN, 0.0);
  }
  fEvtTot.assign(fN, 0.0);
  fIsTouched.assign(fN, 0);
  col_sq.assign(size_t(fNx) * fNy, 0.0);
  fEvtCol.assign(size_t(fNx) * fNy, 0.0);
  fIsColTouched.assign(size_t(fNx) * fNy, 0);
  fTouched.reserve(256);
}

int VoxelScorer::Bin(const std::vector<double>& e, double v) {
  if (v < e.front() || v >= e.back()) return -1;
  return int(std::upper_bound(e.begin(), e.end(), v) - e.begin()) - 1;
}

long VoxelScorer::Locate(double x, double y, double zrel) const {
  const int ix = Bin(fX, x);
  if (ix < 0) return -1;
  const int iy = Bin(fY, y);
  if (iy < 0) return -1;
  const int iz = Bin(fZ, zrel);
  if (iz < 0) return -1;
  return (long(ix) * fNy + iy) * fNz + iz;  // C-порядок [x][y][z]
}

void VoxelScorer::Add(long idx, double e, Flags f) {
  total[idx] += e;
  if (!fIsTouched[idx]) {
    fIsTouched[idx] = 1;
    fTouched.push_back(idx);
  }
  fEvtTot[idx] += e;
  const long col = idx / fNz;
  fEvtCol[col] += e;
  if (!fIsColTouched[col]) {
    fIsColTouched[col] = 1;
    fColTouched.push_back(col);
  }
  if (!cat.empty()) {
    cat[size_t(Classify(f)) * fN + idx] += e;
    for (int i = 0; i < kNFeatures; ++i)
      if (HasFeature(f, i)) feat[size_t(i) * fN + idx] += e;
    if (HasFeature(f, kF_MembraneAnyScatter)) fEvtMem[idx] += e;
  }
}

void VoxelScorer::EndEvent() {
  for (long idx : fTouched) {
    total_sq[idx] += fEvtTot[idx] * fEvtTot[idx];
    fEvtTot[idx] = 0;
    if (!cat.empty()) {
      mem_sq[idx] += fEvtMem[idx] * fEvtMem[idx];
      fEvtMem[idx] = 0;
    }
    fIsTouched[idx] = 0;
  }
  fTouched.clear();
  for (long c : fColTouched) {
    col_sq[c] += fEvtCol[c] * fEvtCol[c];
    fEvtCol[c] = 0;
    fIsColTouched[c] = 0;
  }
  fColTouched.clear();
}

void VoxelScorer::Merge(const VoxelScorer& o) {
  auto add = [](std::vector<double>& a, const std::vector<double>& b) {
    for (size_t i = 0; i < a.size(); ++i) a[i] += b[i];
  };
  add(total, o.total);
  add(total_sq, o.total_sq);
  add(cat, o.cat);
  add(feat, o.feat);
  add(mem_sq, o.mem_sq);
  add(col_sq, o.col_sq);
}

// ----------------------------------------------------------------- ThreadData
ThreadData::ThreadData(const Config& c) {
  for (const auto& g : c.scoring.grids) grids.push_back(std::make_unique<VoxelScorer>(g));
  nE = c.scoring.spectrum_nbins;
  eMin = c.scoring.spectrum_emin_keV;
  eMax = c.scoring.spectrum_emax_keV;
  entrySpec.assign(size_t(kNRegions) * kNEntryClasses * nE, 0.0);
  entryEnergy.assign(size_t(kNRegions) * kNEntryClasses * nE, 0.0);
  edepByPrimE.assign(size_t(kNRegions) * nE, 0.0);
  edepByPrimEMem.assign(size_t(kNRegions) * nE, 0.0);
  regionEdep.assign(size_t(kNRegions) * kNCategories, 0.0);
  eDepByRole.assign(kNRoles, 0.0);
  slabFirst.assign(4, 0);
  for (const auto& l : c.layers)
    if (l.hole.present) {
      fHoleCx = l.hole.center_x_um * um;
      fHoleCy = l.hole.center_y_um * um;
      fHoleAx = 0.5 * l.hole.size_x_um * um;
      fHoleAy = 0.5 * l.hole.size_y_um * um;
    }
  fMargin = c.scoring.region_margin_um * um;
}

int ThreadData::RegionOf(double x, double y) const {
  if (fHoleAx < 0) return 0;  // поглотителя нет — вся площадь «открыта»
  const double dx = std::abs(x - fHoleCx), dy = std::abs(y - fHoleCy);
  if (dx < fHoleAx - fMargin && dy < fHoleAy - fMargin) return 0;
  if (dx > fHoleAx + fMargin || dy > fHoleAy + fMargin) return 2;
  return 1;
}

int ThreadData::EBin(double e_keV) const {
  if (e_keV < eMin || e_keV >= eMax) return -1;
  return int((e_keV - eMin) / (eMax - eMin) * nE);
}

void ThreadData::EndEvent() {
  for (auto& g : grids) g->EndEvent();
  ++nEvents;
  if (psBuffer.size() >= 4096) FlushPS();
}

void ThreadData::FlushPS() {
  if (psOut && !psBuffer.empty())
    psOut->write(reinterpret_cast<const char*>(psBuffer.data()), std::streamsize(psBuffer.size() * sizeof(PSRecord)));
  psBuffer.clear();
}

void ThreadData::Merge(const ThreadData& o) {
  for (size_t i = 0; i < grids.size(); ++i) grids[i]->Merge(*o.grids[i]);
  auto add = [](std::vector<double>& a, const std::vector<double>& b) {
    for (size_t i = 0; i < a.size(); ++i) a[i] += b[i];
  };
  add(entrySpec, o.entrySpec);
  add(entryEnergy, o.entryEnergy);
  add(edepByPrimE, o.edepByPrimE);
  add(edepByPrimEMem, o.edepByPrimEMem);
  add(regionEdep, o.regionEdep);
  add(eDepByRole, o.eDepByRole);
  eIncident += o.eIncident;
  eEscape += o.eEscape;
  eKilledStack += o.eKilledStack;
  eKilledPlane += o.eKilledPlane;
  sumW += o.sumW;
  sumW2 += o.sumW2;
  nEvents += o.nEvents;
  slabPrimaries += o.slabPrimaries;
  slabUnscattered += o.slabUnscattered;
  for (int i = 0; i < 4; ++i) slabFirst[i] += o.slabFirst[i];
  psCount += o.psCount;
  psSumW += o.psSumW;
}

}  // namespace liga

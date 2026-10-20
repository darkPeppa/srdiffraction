// Модульные тесты C++ без транспорта: критерии заданы заранее (см. docs/validation.md).
#include "HistoryFlags.hh"
#include "PrimaryGeneratorAction.hh"
#include "Scoring.hh"

#include <G4SystemOfUnits.hh>

#include <cmath>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <random>

using namespace liga;

static int gFail = 0;
#define CHECK(cond)                                                           \
  do {                                                                        \
    if (!(cond)) {                                                            \
      std::cerr << "FAIL " << __FILE__ << ":" << __LINE__ << "  " #cond "\n"; \
      ++gFail;                                                                \
    }                                                                         \
  } while (0)

// 1. Каждая маска попадает ровно в одну категорию; ключевые случаи — в ожидаемую.
static void TestClassification() {
  CHECK(Classify(0) == kDirect);
  CHECK(Classify(OriginBit(Role::PMMA)) == kDirect);
  CHECK(Classify(RaylBit(Role::TestMembrane)) == kMembraneRayleighOnly);
  CHECK(Classify(RaylBit(Role::TestMembrane) | ComptBit(Role::TestMembrane)) == kMembraneCompton);
  CHECK(Classify(ComptBit(Role::AlFilter) | RaylBit(Role::TestMembrane)) == kMembraneRayleighOnly);  // приоритет мембраны
  CHECK(Classify(ComptBit(Role::AlFilter)) == kAlFilterScatter);
  CHECK(Classify(RaylBit(Role::MaskSupport)) == kMaskSupportScatter);
  CHECK(Classify(RaylBit(Role::Absorber)) == kOtherScatter);
  CHECK(Classify(ComptBit(Role::PMMA)) == kPMMASelfScatter);
  CHECK(Classify(OriginBit(Role::MaskSupport)) == kExternalSecondary);   // флуоресценция Ti
  CHECK(Classify(OriginBit(Role::TestMembrane) | OriginBit(Role::PMMA)) == kExternalSecondary);
  // Фотопоглощение не является рассеянием: только ORIGIN-бит, без RAYL/COMPT.
  CHECK(!HasFeature(OriginBit(Role::TestMembrane), kF_MembraneAnyScatter));
  // Полный перебор: Classify всегда в [0, kNCategories).
  std::mt19937 rng(1);
  for (int i = 0; i < 200000; ++i) {
    Flags f = rng();
    const int c = Classify(f);
    CHECK(c >= 0 && c < kNCategories);
    if (HasFeature(f, kF_MembraneAnyScatter)) CHECK(c == kMembraneRayleighOnly || c == kMembraneCompton);
  }
}

// 2. Сетка: границы, индексация, сумма квадратов по историям.
static void TestVoxelScorer() {
  GridSpec g;
  g.name = "t";
  g.x_edges_um = {-10, 0, 5, 10};
  g.y_edges_um = {-1, 1};
  g.z_edges_um = {0, 7.5, 15};
  g.categories = true;
  VoxelScorer v(g);
  CHECK(v.NVox() == 3 * 1 * 2);
  CHECK(v.Locate(-10.5 * um, 0, 1 * um) == -1);
  CHECK(v.Locate(10 * um, 0, 1 * um) == -1);  // правая граница исключена
  const long i = v.Locate(2 * um, 0, 8 * um);
  CHECK(i == (1 * 1 + 0) * 2 + 1);
  // Два вклада в одном событии → квадрат суммы, а не сумма квадратов.
  v.Add(i, 1.0, 0);
  v.Add(i, 2.0, RaylBit(Role::TestMembrane));
  v.EndEvent();
  v.Add(i, 3.0, 0);
  v.EndEvent();
  CHECK(std::abs(v.total[i] - 6.0) < 1e-12);
  CHECK(std::abs(v.total_sq[i] - (9.0 + 9.0)) < 1e-12);
  CHECK(std::abs(v.mem_sq[i] - 4.0) < 1e-12);
  // Колонка (x,y): вклады в разные z одного события складываются до возведения в квадрат.
  const long j = v.Locate(2 * um, 0, 1 * um);  // та же колонка, другой z
  v.Add(i, 1.0, 0);
  v.Add(j, 1.0, 0);
  v.EndEvent();
  CHECK(std::abs(v.col_sq[i / 2] - (9.0 + 9.0 + 4.0)) < 1e-12);
  double sumCat = 0;
  for (int c = 0; c < kNCategories; ++c) sumCat += v.cat[size_t(c) * v.NVox() + i];
  CHECK(std::abs(sumCat - v.total[i]) < 1e-12);  // разложение полное
}

// 3. Таблица источника: CDF и колонки по psi.
static void TestSRTable() {
  const char* path = "/tmp/liga_unit_table.csv";
  {
    std::ofstream o(path);
    o << "# test\n"
      << "e_lo_keV,e_hi_keV,psi_lo_mrad,psi_hi_mrad,w_sigma,w_pi\n"
      << "5,6,-0.1,0,1,0\n5,6,0,0.1,3,1\n6,7,-0.1,0,0,0\n6,7,0,0.1,5,0\n";
  }
  auto t = SRTable::Load(path);
  CHECK(t->eLo.size() == 4);
  CHECK(std::abs(t->totalWeight - 10.0) < 1e-12);
  CHECK(t->psiEdges.size() == 3);
  CHECK(t->colRows.size() == 2);
  CHECK(t->colRows[0].size() == 2 && t->colRows[1].size() == 2);
  CHECK(std::abs(t->colCdf[1].back() - 9.0) < 1e-12);
  std::remove(path);
}

int main() {
  TestClassification();
  TestVoxelScorer();
  TestSRTable();
  if (gFail) {
    std::cerr << gFail << " check(s) failed\n";
    return 1;
  }
  std::cout << "liga_unit_tests: all checks passed\n";
  return 0;
}

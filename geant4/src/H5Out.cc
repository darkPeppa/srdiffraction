#include "H5Out.hh"

#include <G4SystemOfUnits.hh>
#include <G4Version.hh>
#include <G4Threading.hh>
#include <hdf5.h>

#include <ctime>
#include <sstream>
#include <stdexcept>
#include <type_traits>
#include <vector>

namespace liga {

namespace {

void Check(herr_t s, const char* what) {
  if (s < 0) throw std::runtime_error(std::string("HDF5 error: ") + what);
}

void AttrStr(hid_t obj, const char* name, const std::string& v) {
  hid_t t = H5Tcopy(H5T_C_S1);
  H5Tset_size(t, v.empty() ? 1 : v.size());
  H5Tset_cset(t, H5T_CSET_UTF8);
  hid_t sp = H5Screate(H5S_SCALAR);
  hid_t a = H5Acreate2(obj, name, t, sp, H5P_DEFAULT, H5P_DEFAULT);
  Check(H5Awrite(a, t, v.empty() ? "" : v.c_str()), name);
  H5Aclose(a); H5Sclose(sp); H5Tclose(t);
}

void AttrD(hid_t obj, const char* name, double v) {
  hid_t sp = H5Screate(H5S_SCALAR);
  hid_t a = H5Acreate2(obj, name, H5T_NATIVE_DOUBLE, sp, H5P_DEFAULT, H5P_DEFAULT);
  Check(H5Awrite(a, H5T_NATIVE_DOUBLE, &v), name);
  H5Aclose(a); H5Sclose(sp);
}

void AttrI(hid_t obj, const char* name, long long v) {
  hid_t sp = H5Screate(H5S_SCALAR);
  hid_t a = H5Acreate2(obj, name, H5T_NATIVE_LLONG, sp, H5P_DEFAULT, H5P_DEFAULT);
  Check(H5Awrite(a, H5T_NATIVE_LLONG, &v), name);
  H5Aclose(a); H5Sclose(sp);
}

template <typename T>
void Dset(hid_t loc, const char* name, const std::vector<T>& data, const std::vector<hsize_t>& dims) {
  hsize_t n = 1;
  for (auto d : dims) n *= d;
  if (n != data.size()) throw std::runtime_error(std::string("HDF5 dims mismatch for ") + name);
  hid_t sp = H5Screate_simple(int(dims.size()), dims.data(), nullptr);
  hid_t plist = H5Pcreate(H5P_DATASET_CREATE);
  if (n > 4096) {  // сжатие крупных массивов (много нулей в сетках)
    Check(H5Pset_chunk(plist, int(dims.size()), dims.data()), "chunk");
    H5Pset_shuffle(plist);
    H5Pset_deflate(plist, 4);
  }
  const hid_t ty = std::is_same<T, double>::value ? H5T_NATIVE_DOUBLE : H5T_NATIVE_LLONG;
  hid_t ds = H5Dcreate2(loc, name, ty, sp, H5P_DEFAULT, plist, H5P_DEFAULT);
  Check(H5Dwrite(ds, ty, H5S_ALL, H5S_ALL, H5P_DEFAULT, data.data()), name);
  H5Dclose(ds); H5Pclose(plist); H5Sclose(sp);
}

std::string Join(const char* (*f)(int), int n) {
  std::string s;
  for (int i = 0; i < n; ++i) { if (i) s += ","; s += f(i); }
  return s;
}
const char* RoleNameI(int i) { return RoleName(static_cast<Role>(i)); }

}  // namespace

void WriteHDF5(const std::string& path, const Config& c, const ThreadData& d, long long nEvents, double wall) {
  hid_t f = H5Fcreate(path.c_str(), H5F_ACC_TRUNC, H5P_DEFAULT, H5P_DEFAULT);
  if (f < 0) throw std::runtime_error("cannot create " + path);

  // ---- метаданные
  hid_t meta = H5Gcreate2(f, "meta", H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
  AttrStr(meta, "config_json", c.raw_json);
  AttrStr(meta, "geant4_version", G4Version);
  AttrStr(meta, "run_name", c.run.name);
  AttrStr(meta, "physics_em", c.physics.em);
  AttrStr(meta, "source_mode", c.source.mode);
  AttrI(meta, "n_events", nEvents);
  AttrI(meta, "seed", c.run.seed);
  AttrI(meta, "threads", G4Threading::GetNumberOfRunningWorkerThreads());
  AttrD(meta, "wall_time_s", wall);
  std::time_t now = std::time(nullptr);
  char buf[64];
  std::strftime(buf, sizeof buf, "%Y-%m-%dT%H:%M:%SZ", std::gmtime(&now));
  AttrStr(meta, "created_utc", buf);
  AttrStr(meta, "liga_sim_version", "1.0.0");
  H5Gclose(meta);

  // ---- баланс энергии (МэВ * вес)
  hid_t b = H5Gcreate2(f, "balance", H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
  AttrD(b, "e_incident_MeV", d.eIncident / MeV);
  AttrD(b, "e_escape_MeV", d.eEscape / MeV);
  AttrD(b, "e_killed_stack_MeV", d.eKilledStack / MeV);
  AttrD(b, "e_killed_plane_MeV", d.eKilledPlane / MeV);
  AttrD(b, "sum_w", d.sumW);
  AttrD(b, "sum_w2", d.sumW2);
  AttrI(b, "n_events", d.nEvents);
  std::vector<double> er(d.eDepByRole.size());
  for (size_t i = 0; i < er.size(); ++i) er[i] = d.eDepByRole[i] / MeV;
  Dset(b, "edep_by_role_MeV", er, {hsize_t(er.size())});
  AttrStr(b, "role_names", Join(RoleNameI, kNRoles));
  H5Gclose(b);

  // ---- сетки
  hid_t gg = H5Gcreate2(f, "grids", H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
  for (const auto& g : d.grids) {
    hid_t gr = H5Gcreate2(gg, g->Spec().name.c_str(), H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
    Dset(gr, "x_edges_um", g->Spec().x_edges_um, {hsize_t(g->Spec().x_edges_um.size())});
    Dset(gr, "y_edges_um", g->Spec().y_edges_um, {hsize_t(g->Spec().y_edges_um.size())});
    Dset(gr, "z_edges_um", g->Spec().z_edges_um, {hsize_t(g->Spec().z_edges_um.size())});
    const std::vector<hsize_t> dims = {hsize_t(g->Nx()), hsize_t(g->Ny()), hsize_t(g->Nz())};
    auto scaled = [](const std::vector<double>& v, double s) {
      std::vector<double> o(v.size());
      for (size_t i = 0; i < v.size(); ++i) o[i] = v[i] * s;
      return o;
    };
    Dset(gr, "edep_MeV", scaled(g->total, 1.0 / MeV), dims);
    Dset(gr, "edep_sq_MeV2", scaled(g->total_sq, 1.0 / (MeV * MeV)), dims);
    Dset(gr, "column_sq_MeV2", scaled(g->col_sq, 1.0 / (MeV * MeV)), {dims[0], dims[1]});
    if (!g->cat.empty()) {
      Dset(gr, "edep_category_MeV", scaled(g->cat, 1.0 / MeV), {hsize_t(kNCategories), dims[0], dims[1], dims[2]});
      Dset(gr, "edep_feature_MeV", scaled(g->feat, 1.0 / MeV), {hsize_t(kNFeatures), dims[0], dims[1], dims[2]});
      Dset(gr, "edep_membrane_sq_MeV2", scaled(g->mem_sq, 1.0 / (MeV * MeV)), dims);
      AttrStr(gr, "category_names", Join(CategoryName, kNCategories));
      AttrStr(gr, "feature_names", Join(FeatureName, kNFeatures));
    }
    H5Gclose(gr);
  }
  H5Gclose(gg);

  // ---- спектры и регионы
  hid_t sp = H5Gcreate2(f, "spectra", H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
  std::vector<double> edges(d.nE + 1);
  for (int i = 0; i <= d.nE; ++i) edges[i] = d.eMin + (d.eMax - d.eMin) * i / d.nE;
  Dset(sp, "e_edges_keV", edges, {hsize_t(edges.size())});
  const hsize_t R = ThreadData::kNRegions, K = ThreadData::kNEntryClasses, N = hsize_t(d.nE);
  std::vector<double> ee(d.entryEnergy.size());
  for (size_t i = 0; i < ee.size(); ++i) ee[i] = d.entryEnergy[i] / MeV;
  Dset(sp, "pmma_entry_weight", d.entrySpec, {R, K, N});
  Dset(sp, "pmma_entry_energy_MeV", ee, {R, K, N});
  std::vector<double> a(d.edepByPrimE.size()), m(d.edepByPrimEMem.size()), re(d.regionEdep.size());
  for (size_t i = 0; i < a.size(); ++i) { a[i] = d.edepByPrimE[i] / MeV; m[i] = d.edepByPrimEMem[i] / MeV; }
  for (size_t i = 0; i < re.size(); ++i) re[i] = d.regionEdep[i] / MeV;
  Dset(sp, "edep_by_primary_energy_MeV", a, {R, N});
  Dset(sp, "edep_by_primary_energy_membrane_MeV", m, {R, N});
  Dset(sp, "region_edep_by_category_MeV", re, {R, hsize_t(kNCategories)});
  AttrStr(sp, "region_names", "open,edge,shadow");
  AttrStr(sp, "entry_class_names", "unscattered,membrane_scattered,other");
  AttrStr(sp, "category_names", Join(CategoryName, kNCategories));
  AttrD(sp, "region_margin_um", c.scoring.region_margin_um);
  H5Gclose(sp);

  // ---- тест пластины
  if (c.scoring.slab_test) {
    hid_t s = H5Gcreate2(f, "slab", H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
    AttrI(s, "primaries", d.slabPrimaries);
    AttrI(s, "unscattered_transmitted", d.slabUnscattered);
    AttrI(s, "first_rayleigh", d.slabFirst[0]);
    AttrI(s, "first_compton", d.slabFirst[1]);
    AttrI(s, "first_photoelectric", d.slabFirst[2]);
    AttrI(s, "first_other", d.slabFirst[3]);
    AttrStr(s, "layer", c.scoring.slab_layer);
    H5Gclose(s);
  }

  // ---- фазовое пространство
  if (c.scoring.phase_space_out) {
    hid_t s = H5Gcreate2(f, "phase_space", H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
    AttrI(s, "records", d.psCount);
    AttrD(s, "sum_w", d.psSumW);
    AttrI(s, "n_primaries", nEvents);
    AttrStr(s, "file_prefix", c.scoring.phase_space_file);
    AttrD(s, "plane_z_mm", c.scoring.phase_space_plane_z_mm);
    AttrI(s, "record_bytes", (long long)sizeof(PSRecord));
    AttrStr(s, "record_fields", "e_keV:f8,x_mm:f8,y_mm:f8,dx_mm:f8,dy_mm:f8,ux:f8,uy:f8,uz:f8,px:f8,py:f8,pz:f8,w:f8,ylab_mm:f8,flags:u4,pdg:i4,event:i8");
    H5Gclose(s);
  }
  H5Fclose(f);
}

}  // namespace liga

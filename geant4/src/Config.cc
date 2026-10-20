#include "Config.hh"

#include <nlohmann/json.hpp>

#include <fstream>
#include <memory>
#include <sstream>
#include <stdexcept>

namespace liga {

using json = nlohmann::json;

namespace {

std::unique_ptr<Config> gConfig;

template <typename T>
T Opt(const json& j, const char* key, const T& def) {
  auto it = j.find(key);
  if (it == j.end() || it->is_null()) return def;
  return it->get<T>();
}

template <typename T>
T Req(const json& j, const char* key, const std::string& ctx) {
  auto it = j.find(key);
  if (it == j.end() || it->is_null())
    throw std::runtime_error("config: required field '" + std::string(key) + "' missing in " + ctx);
  return it->get<T>();
}

}  // namespace

Role RoleFromString(const std::string& s) {
  for (int i = 0; i < kNRoles; ++i)
    if (s == RoleName(static_cast<Role>(i))) return static_cast<Role>(i);
  throw std::runtime_error("config: unknown layer role '" + s + "'");
}

Config Config::Load(const std::string& path) {
  std::ifstream in(path);
  if (!in) throw std::runtime_error("config: cannot open " + path);
  std::stringstream ss;
  ss << in.rdbuf();
  Config c;
  c.raw_json = ss.str();
  const json j = json::parse(c.raw_json);

  // --- run
  const json& r = j.at("run");
  c.run.name = Opt<std::string>(r, "name", "run");
  c.run.mode = Opt<std::string>(r, "mode", "transport");
  c.run.n_events = Opt<long long>(r, "n_events", 1000);
  c.run.seed = Opt<long>(r, "seed", 12345);
  c.run.threads = Opt<int>(r, "threads", 0);
  c.run.output = Req<std::string>(r, "output", "run");
  c.run.progress_every = Opt<long long>(r, "progress_every", 0);
  c.run.xs_energies_keV = Opt<std::vector<double>>(r, "xs_energies_keV", {});
  c.run.xs_output = Opt<std::string>(r, "xs_output", "");
  c.run.ui_commands = Opt<std::vector<std::string>>(r, "ui_commands", {});
  c.run.ui_commands_after = Opt<std::vector<std::string>>(r, "ui_commands_after", {});

  // --- physics
  if (j.contains("physics")) {
    const json& p = j.at("physics");
    c.physics.em = Opt<std::string>(p, "em", "livermore");
    c.physics.fluo = Opt<bool>(p, "fluo", true);
    c.physics.auger = Opt<bool>(p, "auger", true);
    c.physics.pixe = Opt<bool>(p, "pixe", false);
    c.physics.deexcitation_ignore_cut = Opt<bool>(p, "deexcitation_ignore_cut", true);
    c.physics.default_cut_um = Opt<double>(p, "default_cut_um", 1.0);
    c.physics.lowest_electron_energy_eV = Opt<double>(p, "lowest_electron_energy_eV", 100.0);
    c.physics.cuts_table_low_edge_eV = Opt<double>(p, "cuts_table_low_edge_eV", 100.0);
    c.physics.kill_unreachable_electrons = Opt<bool>(p, "kill_unreachable_electrons", true);
    c.physics.pmma_max_step_um = Opt<double>(p, "pmma_max_step_um", 0.0);
    c.physics.force_collision_roles = Opt<std::vector<std::string>>(p, "force_collision_roles", {});
    for (const auto& r : c.physics.force_collision_roles) RoleFromString(r);  // проверка имён
  }

  // --- world
  const json& w = j.at("world");
  c.world_material = Req<std::string>(w, "material", "world");
  c.world_half_xy_mm = Req<double>(w, "half_xy_mm", "world");
  c.world_half_z_mm = Req<double>(w, "half_z_mm", "world");

  // --- materials
  for (auto& [name, m] : j.at("materials").items()) {
    MaterialSpec ms;
    ms.name = name;
    ms.nist = Opt<std::string>(m, "nist", "");
    ms.density_g_cm3 = Opt<double>(m, "density_g_cm3", 0.0);
    ms.mass_fractions = Opt<std::map<std::string, double>>(m, "mass_fractions", {});
    ms.atoms = Opt<std::map<std::string, int>>(m, "atoms", {});
    ms.state = Opt<std::string>(m, "state", "solid");
    ms.temperature_K = Opt<double>(m, "temperature_K", 293.15);
    ms.pressure_Pa = Opt<double>(m, "pressure_Pa", 101325.0);
    if (ms.nist.empty() && ms.density_g_cm3 <= 0)
      throw std::runtime_error("config: material '" + name + "' needs nist or density");
    c.materials[name] = ms;
  }

  // --- layers
  for (const json& l : j.at("layers")) {
    LayerSpec ls;
    ls.name = Req<std::string>(l, "name", "layer");
    ls.role = RoleFromString(Req<std::string>(l, "role", ls.name));
    ls.material = Req<std::string>(l, "material", ls.name);
    ls.thickness_um = Req<double>(l, "thickness_um", ls.name);
    ls.z_front_mm = Req<double>(l, "z_front_mm", ls.name);
    ls.half_x_mm = Req<double>(l, "half_x_mm", ls.name);
    ls.half_y_mm = Req<double>(l, "half_y_mm", ls.name);
    ls.prod_cut_um = Opt<double>(l, "prod_cut_um", -1.0);
    if (l.contains("hole") && !l.at("hole").is_null()) {
      const json& h = l.at("hole");
      ls.hole.present = true;
      ls.hole.size_x_um = Req<double>(h, "size_x_um", ls.name + ".hole");
      ls.hole.size_y_um = Opt<double>(h, "size_y_um", ls.hole.size_x_um);
      ls.hole.center_x_um = Opt<double>(h, "center_x_um", 0.0);
      ls.hole.center_y_um = Opt<double>(h, "center_y_um", 0.0);
    }
    if (!c.materials.count(ls.material) && ls.material.rfind("G4_", 0) != 0)
      throw std::runtime_error("config: layer '" + ls.name + "' uses undefined material '" + ls.material + "'");
    if (ls.thickness_um <= 0) throw std::runtime_error("config: layer '" + ls.name + "' has non-positive thickness");
    c.layers.push_back(ls);
  }

  // --- scoring
  if (j.contains("scoring")) {
    const json& s = j.at("scoring");
    c.scoring.pmma_layer = Opt<std::string>(s, "pmma_layer", "PMMA");
    if (s.contains("grids")) {
      for (const json& g : s.at("grids")) {
        GridSpec gs;
        gs.name = Req<std::string>(g, "name", "grid");
        gs.x_edges_um = Req<std::vector<double>>(g, "x_edges_um", gs.name);
        gs.y_edges_um = Req<std::vector<double>>(g, "y_edges_um", gs.name);
        gs.z_edges_um = Req<std::vector<double>>(g, "z_edges_um", gs.name);
        gs.categories = Opt<bool>(g, "categories", true);
        c.scoring.grids.push_back(gs);
      }
    }
    c.scoring.spectrum_emin_keV = Opt<double>(s, "spectrum_emin_keV", 0.0);
    c.scoring.spectrum_emax_keV = Opt<double>(s, "spectrum_emax_keV", 80.0);
    c.scoring.spectrum_nbins = Opt<int>(s, "spectrum_nbins", 400);
    c.scoring.region_margin_um = Opt<double>(s, "region_margin_um", 5.0);
    c.scoring.phase_space_out = Opt<bool>(s, "phase_space_out", false);
    c.scoring.phase_space_plane_z_mm = Opt<double>(s, "phase_space_plane_z_mm", 0.0);
    c.scoring.phase_space_file = Opt<std::string>(s, "phase_space_file", "");
    c.scoring.slab_test = Opt<bool>(s, "slab_test", false);
    c.scoring.slab_layer = Opt<std::string>(s, "slab_layer", "");
  }

  // --- source
  if (j.contains("source")) {
    const json& s = j.at("source");
    c.source.mode = Opt<std::string>(s, "mode", "sr_table");
    c.source.table_file = Opt<std::string>(s, "table_file", "");
    c.source.phase_space_files = Opt<std::string>(s, "phase_space_files", "");
    c.source.gps_macro = Opt<std::string>(s, "gps_macro", "");
    c.source.pencil_energy_keV = Opt<double>(s, "pencil_energy_keV", 10.0);
    c.source.z_mm = Req<double>(s, "z_mm", "source");
    c.source.distance_m = Opt<double>(s, "distance_m", 20.3);
    c.source.window_half_x_mm = Opt<double>(s, "window_half_x_mm", 1.0);
    c.source.window_half_y_mm = Opt<double>(s, "window_half_y_mm", 1.0);
    c.source.core_half_x_mm = Opt<double>(s, "core_half_x_mm", 0.0);
    c.source.core_half_y_mm = Opt<double>(s, "core_half_y_mm", 0.0);
    c.source.core_fraction = Opt<double>(s, "core_fraction", 0.0);
    c.source.scan_mode = Opt<std::string>(s, "scan_mode", "averaged");
    c.source.scan_half_amplitude_mm = Opt<double>(s, "scan_half_amplitude_mm", 15.0);
    c.source.hole_offset_x_mm = Opt<double>(s, "hole_offset_x_mm", 0.0);
    c.source.hole_offset_y_mm = Opt<double>(s, "hole_offset_y_mm", 0.0);
    c.source.source_sigma_x_mm = Opt<double>(s, "source_sigma_x_mm", 0.0);
    c.source.source_sigma_y_mm = Opt<double>(s, "source_sigma_y_mm", 0.0);
    c.source.electron_divergence_sigma_mrad = Opt<double>(s, "electron_divergence_sigma_mrad", 0.0);
    c.source.polarization = Opt<bool>(s, "polarization", true);
    c.source.beam_half_x_mm = Opt<double>(s, "beam_half_x_mm", 36.0);
    c.source.ps_n_primaries = Opt<double>(s, "ps_n_primaries", 0.0);
    if (c.source.core_fraction < 0 || c.source.core_fraction >= 1)
      throw std::runtime_error("config: source.core_fraction must be in [0,1)");
  }
  return c;
}

const LayerSpec* Config::FindLayer(const std::string& name) const {
  for (const auto& l : layers)
    if (l.name == name) return &l;
  return nullptr;
}

const Config& Cfg() {
  if (!gConfig) throw std::runtime_error("config not loaded");
  return *gConfig;
}

void SetGlobalConfig(const Config& c) { gConfig = std::make_unique<Config>(c); }

}  // namespace liga

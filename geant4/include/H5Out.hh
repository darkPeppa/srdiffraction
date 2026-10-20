// =============================================================================
//  H5Out — запись результатов запуска в HDF5 (открытый формат; схема описана
//  в docs/normalization.md и читается python/analysis/io.py).
// =============================================================================
#pragma once

#include "Config.hh"
#include "Scoring.hh"

#include <string>

namespace liga {

void WriteHDF5(const std::string& path, const Config& cfg, const ThreadData& d, long long nEvents, double wallSeconds);

}  // namespace liga

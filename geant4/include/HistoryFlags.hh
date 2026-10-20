// =============================================================================
//  HistoryFlags — метки истории взаимодействий трека.
//
//  Каждый трек несёт 32-битную маску. Для каждой «роли» объёма (Be-окно,
//  Al-фильтр, исследуемая мембрана, ...) зарезервировано три бита:
//    RAYL   — фотон этой истории испытал рэлеевское рассеяние в объёме роли;
//    COMPT  — испытал комптоновское рассеяние;
//    ORIGIN — частица (или её предок) родилась в объёме роли НЕ в результате
//             рассеяния (фотоэлектрон, флуоресценция, оже-электрон и т.п.).
//  Вторичные частицы наследуют маску родителя и добавляют свой ORIGIN-бит.
//
//  Важно: фотопоглощение НЕ считается рассеянием (требование ТЗ, п.7.1).
//
//  Из маски строятся:
//   (1) непересекающиеся категории (полное разложение энерговыделения),
//   (2) перекрывающиеся признаки «в истории было рассеяние в материале m».
// =============================================================================
#pragma once

#include <array>
#include <cstdint>
#include <string>

namespace liga {

enum class Role : std::uint8_t {
  Gas = 0,           // мировой объём / газовые промежутки
  BeWindow = 1,      // бериллиевые окна канала (при явном моделировании)
  AlFilter = 2,      // алюминиевый фильтр
  TestMembrane = 3,  // исследуемая мембрана (Be, стеклоуглерод, Al2O3, Ti-модель)
  MaskSupport = 4,   // титановая основа рентгеношаблона (MaskSupport_Ti)
  Absorber = 5,      // золотой поглотитель с отверстием
  Kapton = 6,        // каптоновая плёнка
  PMMA = 7,          // резист (чувствительный объём)
  Substrate = 8,     // подложка под ПММА (если задана)
  Other = 9,         // прочие слои (тестовые пластины и т.п.)
  NRoles = 10
};

constexpr int kNRoles = static_cast<int>(Role::NRoles);

inline const char* RoleName(Role r) {
  switch (r) {
    case Role::Gas: return "gas";
    case Role::BeWindow: return "be_window";
    case Role::AlFilter: return "al_filter";
    case Role::TestMembrane: return "test_membrane";
    case Role::MaskSupport: return "mask_support";
    case Role::Absorber: return "absorber";
    case Role::Kapton: return "kapton";
    case Role::PMMA: return "pmma";
    case Role::Substrate: return "substrate";
    case Role::Other: return "other";
    default: return "unknown";
  }
}

Role RoleFromString(const std::string& s);  // реализовано в Config.cc

using Flags = std::uint32_t;

constexpr Flags RaylBit(Role r) { return Flags(1u) << (3 * static_cast<int>(r) + 0); }
constexpr Flags ComptBit(Role r) { return Flags(1u) << (3 * static_cast<int>(r) + 1); }
constexpr Flags OriginBit(Role r) { return Flags(1u) << (3 * static_cast<int>(r) + 2); }
constexpr Flags ScatterBits(Role r) { return RaylBit(r) | ComptBit(r); }

inline Flags AllScatterBits() {
  Flags m = 0;
  for (int i = 0; i < kNRoles; ++i) m |= ScatterBits(static_cast<Role>(i));
  return m;
}
inline Flags AllOriginBits() {
  Flags m = 0;
  for (int i = 0; i < kNRoles; ++i) m |= OriginBit(static_cast<Role>(i));
  return m;
}

// ---------------------------------------------------------------------------
// Непересекающиеся категории (приоритетная схема; сумма = полное Edep).
// ---------------------------------------------------------------------------
enum Category : int {
  kDirect = 0,               // ни одного рассеяния; частица/предки родились только в ПММА
  kMembraneRayleighOnly,     // рассеяние в исследуемой мембране, только рэлеевское
  kMembraneCompton,          // рассеяние в мембране, среди них хотя бы одно комптоновское
  kAlFilterScatter,          // (без рассеяния в мембране) рассеяние в Al-фильтре
  kBeWindowScatter,          // (без указанных выше) рассеяние в Be-окнах
  kMaskSupportScatter,       // (без указанных выше) рассеяние в Ti-основе шаблона
  kOtherScatter,             // (без указанных выше) рассеяние в Au, каптоне, газе, подложке
  kPMMASelfScatter,          // рассеяние только внутри самого ПММА
  kExternalSecondary,        // без рассеяний, но частица родилась вне ПММА
                             // (флуоресценция Ti/Au/мембраны, электроны каптона и т.п.)
  kNCategories
};

inline const char* CategoryName(int c) {
  static const char* names[kNCategories] = {
      "direct",           "membrane_rayleigh_only", "membrane_compton",
      "al_filter_scatter", "be_window_scatter",     "mask_support_scatter",
      "other_scatter",     "pmma_self_scatter",     "external_secondary"};
  return (c >= 0 && c < kNCategories) ? names[c] : "unknown";
}

inline int Classify(Flags f) {
  const Flags mem = ScatterBits(Role::TestMembrane);
  if (f & mem) return (f & ComptBit(Role::TestMembrane)) ? kMembraneCompton : kMembraneRayleighOnly;
  if (f & ScatterBits(Role::AlFilter)) return kAlFilterScatter;
  if (f & ScatterBits(Role::BeWindow)) return kBeWindowScatter;
  if (f & ScatterBits(Role::MaskSupport)) return kMaskSupportScatter;
  const Flags other = ScatterBits(Role::Absorber) | ScatterBits(Role::Kapton) |
                      ScatterBits(Role::Gas) | ScatterBits(Role::Substrate) |
                      ScatterBits(Role::Other);
  if (f & other) return kOtherScatter;
  if (f & ScatterBits(Role::PMMA)) return kPMMASelfScatter;
  if (f & (AllOriginBits() & ~OriginBit(Role::PMMA))) return kExternalSecondary;
  return kDirect;
}

// ---------------------------------------------------------------------------
// Перекрывающиеся признаки (их доли НЕЛЬЗЯ суммировать как части целого).
// ---------------------------------------------------------------------------
enum FlagFeature : int {
  kF_MembraneAnyScatter = 0,
  kF_MembraneRayleigh,
  kF_MembraneCompton,
  kF_AlFilterAnyScatter,
  kF_BeWindowAnyScatter,
  kF_MaskSupportAnyScatter,
  kF_AbsorberAnyScatter,
  kF_AnyScatterOutsidePMMA,
  kF_OriginMembrane,
  kF_OriginAbsorber,
  kF_OriginMaskSupport,
  kF_OriginKapton,
  kNFeatures
};

inline const char* FeatureName(int i) {
  static const char* names[kNFeatures] = {
      "membrane_any_scatter",     "membrane_rayleigh",       "membrane_compton",
      "al_filter_any_scatter",    "be_window_any_scatter",   "mask_support_any_scatter",
      "absorber_any_scatter",     "any_scatter_outside_pmma", "origin_membrane",
      "origin_absorber",          "origin_mask_support",     "origin_kapton"};
  return (i >= 0 && i < kNFeatures) ? names[i] : "unknown";
}

inline bool HasFeature(Flags f, int i) {
  switch (i) {
    case kF_MembraneAnyScatter: return f & ScatterBits(Role::TestMembrane);
    case kF_MembraneRayleigh: return f & RaylBit(Role::TestMembrane);
    case kF_MembraneCompton: return f & ComptBit(Role::TestMembrane);
    case kF_AlFilterAnyScatter: return f & ScatterBits(Role::AlFilter);
    case kF_BeWindowAnyScatter: return f & ScatterBits(Role::BeWindow);
    case kF_MaskSupportAnyScatter: return f & ScatterBits(Role::MaskSupport);
    case kF_AbsorberAnyScatter: return f & ScatterBits(Role::Absorber);
    case kF_AnyScatterOutsidePMMA: return f & (AllScatterBits() & ~ScatterBits(Role::PMMA));
    case kF_OriginMembrane: return f & OriginBit(Role::TestMembrane);
    case kF_OriginAbsorber: return f & OriginBit(Role::Absorber);
    case kF_OriginMaskSupport: return f & OriginBit(Role::MaskSupport);
    case kF_OriginKapton: return f & OriginBit(Role::Kapton);
    default: return false;
  }
}

}  // namespace liga

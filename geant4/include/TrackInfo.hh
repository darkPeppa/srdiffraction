// =============================================================================
//  TrackInfo / PrimaryInfo — пользовательская информация трека и первичной
//  частицы: метки истории, энергия первичного фотона «предка», вертикальное
//  положение старта в лабораторной СК (для весов сканирования на этапе 1).
// =============================================================================
#pragma once

#include "HistoryFlags.hh"

#include <G4VUserPrimaryParticleInformation.hh>
#include <G4VUserTrackInformation.hh>

namespace liga {

class TrackInfo : public G4VUserTrackInformation {
 public:
  Flags flags = 0;
  double primaryEnergy = 0;  // энергия первичного фотона истории (внутр. единицы)
  double yLab = 0;           // лабораторная вертикальная координата старта первичного фотона (мм)
  int nInteractions = 0;     // число взаимодействий данного трека (для тестов пластин)
  int firstProcess = -1;     // 0 Rayl, 1 compt, 2 phot, 3 прочие
  Role birthRole = Role::Gas;
  void Print() const override {}
};

class PrimaryInfo : public G4VUserPrimaryParticleInformation {
 public:
  PrimaryInfo(Flags f, double e, double y, double w) : flags(f), energy(e), yLab(y), weight(w) {}
  Flags flags;
  double energy;
  double yLab;
  double weight;
  void Print() const override {}
};

}  // namespace liga

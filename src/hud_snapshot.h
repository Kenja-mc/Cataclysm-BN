#pragma once

#include <array>
#include <string>
#include <vector>

#include "color.h"

class avatar;

/// Every reading the HUD shows, read once per frame so a layout only arranges text.
namespace hud_snapshot
{

struct need {
    std::string label;
    std::string text;
    nc_color color = c_light_gray;
    /// No action needed.
    bool fine = true;
};

struct limb {
    std::string name;
    int hp = 0;
    int hp_max = 0;
    nc_color color = c_light_gray;
    /// Worst problem, empty when healthy.
    std::string wound;
    nc_color wound_color = c_light_gray;
};

struct compass_cell {
    /// Monster symbols seen in this direction.
    std::string symbols;
    int count = 0;
    bool dangerous = false;
};

struct carried {
    std::string name;
    std::string symbol;
    nc_color color = c_light_gray;
    /// Charges or ammo, empty when the item has none.
    std::string detail;
};

struct snapshot {
    std::string time;
    std::string date;
    std::string weather;
    nc_color weather_color = c_light_gray;
    std::string light;
    nc_color light_color = c_light_gray;
    std::string wind;
    nc_color wind_color = c_light_gray;
    std::string place;
    bool underground = false;

    int hp_percent = 100;
    nc_color hp_color = c_green;
    int stamina = 0;
    int stamina_max = 1;
    int focus = 100;
    int morale = 0;
    int speed = 100;
    int pain_level = 0;
    int move_counter = 0;
    std::string stance;
    nc_color stance_color = c_light_gray;
    std::string sound;

    need pain;
    need thirst;
    need hunger;
    need rest;
    need heat;

    std::string weapon;
    bool armed = false;
    bool gun = false;
    /// "loaded/capacity" for a gun, otherwise empty.
    std::string ammo;
    std::string weapon_symbol;
    nc_color weapon_color = c_light_gray;
    std::string style;

    std::string weight;
    std::string volume;
    double weight_kg = 0.0;
    double volume_l = 0.0;
    nc_color weight_color = c_light_gray;
    nc_color volume_color = c_light_gray;

    bool safe_mode = false;
    nc_color safe_color = c_green;

    int str = 0;
    int dex = 0;
    int intel = 0;
    int per = 0;

    std::vector<limb> limbs;
    /// Newest last; colour tags kept for print_colored_text.
    std::vector<std::string> log;
    /// N, NE, E, SE, S, SW, W, NW, near.
    std::array<compass_cell, 9> compass;
    /// Wielded item first, then the first few carried items.
    std::vector<carried> loadout;
};

auto read( const avatar &you ) -> snapshot;

} // namespace hud_snapshot

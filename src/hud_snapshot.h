#pragma once

#include <string>
#include <vector>

#include "color.h"

class avatar;

namespace hud_snapshot
{

struct need {
    std::string label;
    std::string text;
    nc_color color = c_light_gray;
    bool fine = true;
};

struct limb {
    std::string name;
    int hp = 0;
    int hp_max = 0;
    nc_color color = c_light_gray;
    std::string wound;
    nc_color wound_color = c_light_gray;
};

struct encumbered {
    std::string name;
    int level = 0;
    nc_color color = c_light_gray;
};

struct sighting {
    std::string name;
    std::string symbol;
    nc_color color = c_light_gray;
    std::string direction;
    int distance = 0;
    bool hostile = false;
};

struct carried {
    std::string name;
    std::string symbol;
    nc_color color = c_light_gray;
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
    std::vector<encumbered> encumbered;
    std::vector<std::string> log;
    std::vector<sighting> seen;
    std::vector<carried> loadout;
};

auto read( const avatar &you ) -> snapshot;

}

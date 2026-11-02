#pragma once
#ifndef CATA_SRC_ACTION_PREVIEW_H
#define CATA_SRC_ACTION_PREVIEW_H

#include <string>
#include <string_view>
#include <vector>

#include "bodypart.h"
#include "units_volume.h"

class avatar;
class Character;
class item;
class nc_color;

struct body_change {
    bodypart_id part;
    int before = 0;
    int after = 0;
    int layering_after = 0;
    std::vector<std::string> sharing;
};

struct wear_preview {
    std::vector<body_change> parts;
    int warmth_delta = 0;
    units::volume storage_delta = 0_ml;
    int moves = 0;
};

struct encumbrance_effect_numbers {
    int melee_hit = 0;
    double dodge = 0;
    int swim_cost = 0;
    int melee_cost = 0;
    int perception = 0;
    int dispersion = 0;
    double night_vision = 0;
    int mouth_stamina = 0;
    int melee_stamina = 0;
    double ranged_dispersion = 0;
    int reload_cost = 0;
    double throw_dex = 0;
    int hand_melee_cost = 0;
    double aim_speed = 0;
    int run_cost = 0;
};

auto encumbrance_numbers( const Character &who, const bodypart_str_id &bp, int value )
-> encumbrance_effect_numbers;

auto encumbrance_effects( const Character &who, const bodypart_str_id &bp, int value )
-> std::string;

auto preview_wear( const Character &who, const item &it ) -> wear_preview;

auto describe( const Character &who, const wear_preview &preview ) -> std::vector<std::string>;

auto action_cost( const avatar &who, const item &it, std::string_view action ) -> std::string;

#endif

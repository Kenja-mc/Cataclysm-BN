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

/// One body part's encumbrance change when the item is put on.
struct body_change {
    bodypart_id part;
    int before = 0;
    int after = 0;
    int layering_after = 0;
    std::vector<std::string> sharing;
};

/// What wearing an item would do to the character right now.
struct wear_preview {
    std::vector<body_change> parts;
    int warmth_delta = 0;
    units::volume storage_delta = 0_ml;
    int moves = 0;
};

/// Penalties an encumbrance value produces. The character sheet and the short preview line
/// format the same numbers so they cannot drift apart.
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

/// Color the character sheet gives an encumbrance value.
auto encumb_color( int level ) -> nc_color;

/// Numbers the sheet prints for this body part at this encumbrance.
auto encumbrance_numbers( const Character &who, const bodypart_str_id &bp, int value )
-> encumbrance_effect_numbers;

/// One short line of effects for a body part at this encumbrance.
auto encumbrance_effects( const Character &who, const bodypart_str_id &bp, int value )
-> std::string;

/// Encumbrance, warmth, storage and time cost of wearing @p it.
auto preview_wear( const Character &who, const item &it ) -> wear_preview;

/// Lines describing @p preview, ready to print: changes first, then the summary.
auto describe( const Character &who, const wear_preview &preview ) -> std::vector<std::string>;

/// Short cost annotation the item-action menu prints after an action's label, such as
/// "30 s · torso +13" for WEAR. Empty when the action has no computable cost.
auto action_cost( const avatar &who, const item &it, std::string_view action ) -> std::string;

#endif // CATA_SRC_ACTION_PREVIEW_H

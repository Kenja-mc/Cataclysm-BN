#pragma once

#include <string>
#include <string_view>

#include "coordinates.h"

class Creature;

namespace tile_effects
{

struct overlay_options {
    const Creature &critter;
    const tripoint_bub_ms &pos;
};

auto enabled() -> bool;

auto overlay_tile_id( const overlay_options &opt, int idle_frame ) -> const std::string *;

auto owns_effect( std::string_view effect_id ) -> bool;

}

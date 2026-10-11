#pragma once

#include <string>
#include <string_view>

#include "coordinates.h"

class Creature;

namespace tile_effects
{

/// Everything the looping status overlay of one creature needs.
struct overlay_options {
    const Creature &critter;
    const tripoint_bub_ms &pos;
};

/// Whether the looping status overlays are drawn (Graphics → Status effect animations).
auto enabled() -> bool;

/// Tileset id of the overlay to draw on @p opt.critter right now, or nullptr when the
/// creature has no visible status effect.  @p idle_frame is a wall clock frame, so the
/// loop moves even while no turn passes, and the creature position staggers neighbours.
auto overlay_tile_id( const overlay_options &opt, int idle_frame ) -> const std::string *;

/// True when this module draws the overlay of effect @p effect_id (an effect id such as
/// "onfire", not a tileset id) as a loop, so the generic overlay pass must skip it.
auto owns_effect( std::string_view effect_id ) -> bool;

} // namespace tile_effects

#pragma once

#include <optional>

#include "action.h"
#include "coordinates.h"

class avatar;
class input_context;
class map;

/// Free selection shared by keyboard and mouse.
namespace aim_reticle
{

enum class attack_mode {
    direct,
    fire_command
};

auto enabled() -> bool;

auto active() -> bool;

auto pos() -> std::optional<tripoint_bub_ms>;

/// Free, visible, same-level selection, independent of arrow aiming.
auto select( avatar &you, map &m, const tripoint_bub_ms &p ) -> bool;

/// Wrap visible hostiles by distance/position without spending moves.
auto cycle( avatar &you, map &m, bool reverse = false ) -> bool;

/// True for typed cardinal arrow-key movement.
auto arrow_move( const action_id act, input_context &ctxt ) -> bool;

/// Start at the nearest visible hostile, otherwise the player.
auto move( avatar &you, map &m, const point_rel_ms &delta ) -> void;

/// Keyboard fire may fall back to gun aiming; direct clicks never retarget.
/// ACTION_FIRE: aim; ACTION_NULL: handled; nullopt: no selection.
auto attack( avatar &you, map &m, attack_mode mode ) -> std::optional<action_id>;

/// Return whether a selection was cleared.
auto clear() -> bool;

} // namespace aim_reticle

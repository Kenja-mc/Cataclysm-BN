#pragma once

#include <optional>

#include "action.h"
#include "coordinates.h"

class avatar;
class input_context;
class map;

/// Sword of the Stars: The Pit style aiming. The arrow keys move a targeting reticle over the
/// map without spending a turn and F attacks what it covers; the reticle tile reuses the mouse
/// tile selection highlight and the Mouse View hint.
namespace aim_reticle
{

auto enabled() -> bool;

/// True while the reticle is up, so F attacks the tile it covers.
auto active() -> bool;

auto pos() -> std::optional<tripoint_bub_ms>;

/// True when the action is a cardinal move the player typed on an arrow key.
auto arrow_move( const action_id act, input_context &ctxt ) -> bool;

/// Moves the reticle one step. The first call puts it on the nearest visible hostile, else on the player.
auto move( avatar &you, map &m, const point_rel_ms &delta ) -> void;

/// F with the reticle up. Returns the action to run (ACTION_FIRE to aim at the target),
/// ACTION_NULL when it was already handled, nullopt when there is no reticle.
auto attack( avatar &you, map &m ) -> std::optional<action_id>;

/// Takes the reticle away again; returns true when there was one to take.
auto clear() -> bool;

} // namespace aim_reticle

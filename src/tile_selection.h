#pragma once

#include <optional>
#include <string>
#include <vector>

#include "action.h"
#include "coordinates.h"

class avatar;
class map;

/// MOUSE_MOVE opts into travel; otherwise clicks never walk.
namespace tile_selection
{

struct choice {
    action_id act = ACTION_NULL;
    std::string label;
    /// Travel instead of running act.
    bool travel = false;
};

auto enabled() -> bool;

/// Contextual actions, default first.
auto choices_at( const avatar &you, const tripoint_bub_ms &p ) -> std::vector<choice>;
/// Resolve the action; travel also sets the route.
auto resolve( avatar &you, map &m, const choice &c, const tripoint_bub_ms &p ) -> action_id;

/// Act on an adjacent tile without walking.
auto open_at( const tripoint_bub_ms &p ) -> void;
auto smash_at( const tripoint_bub_ms &p ) -> void;

auto hover( avatar &you, map &m, const std::optional<tripoint_bub_ms> &p ) -> void;
auto clear_hover() -> void;
auto hovered() -> std::optional<tripoint_bub_ms>;
auto hover_path() -> const std::vector<tripoint_bub_ms> &; // *NOPAD*
auto hint() -> std::string;

} // namespace tile_selection

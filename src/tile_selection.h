#pragma once

#include <optional>
#include <string>
#include <vector>

#include "action.h"
#include "coordinates.h"

class avatar;
class map;

/// Sword of the Stars: The Pit style mouse play. Hovering a map tile highlights it, previews the
/// route and says what a click will do; left click does it, right click lists every option.
namespace tile_selection
{

struct choice {
    action_id act = ACTION_NULL;
    std::string label;
    /// Walk there along the previewed route instead of running `act`.
    bool travel = false;
};

auto enabled() -> bool;

/// What can be done with the tile, the default (left click) action first. Empty when nothing.
auto choices_at( const avatar &you, const tripoint_bub_ms &p ) -> std::vector<choice>;
/// Turns a choice into the action the main loop runs; travel also sets the auto-move route.
auto resolve( avatar &you, map &m, const choice &c, const tripoint_bub_ms &p ) -> action_id;

auto hover( avatar &you, map &m, const std::optional<tripoint_bub_ms> &p ) -> void;
auto clear_hover() -> void;
auto hovered() -> std::optional<tripoint_bub_ms>;
auto hover_path() -> const std::vector<tripoint_bub_ms> &; // *NOPAD*
/// "click: attack the zombie" style line for the Mouse View box, empty when nothing is hovered.
auto hint() -> std::string;

} // namespace tile_selection

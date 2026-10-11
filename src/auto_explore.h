#pragma once

#include <cstddef>
#include <functional>
#include <optional>
#include <vector>

#include "coordinates.h"

class avatar;
class map;

/// Auto-explore: walk to the nearest reachable tile that borders ground the player has never seen.
namespace auto_explore
{

struct frontier_options {
    avatar &you;
    map &here;
    /// Give up beyond this many steps.
    int max_dist = 60;
    /// Whether the player knows a tile. Empty means "sees it now or has it in map memory".
    std::function<auto( const tripoint_bub_ms & ) -> bool> is_known;
};

/// Up to `count` tiles on the player's z-level, nearest first, other than the one it stands on,
/// that it can walk to without crossing walls, closed doors, known traps or dangerous fields, and
/// that touch a tile it does not know.
auto frontiers( const frontier_options &opts, size_t count ) -> std::vector<tripoint_bub_ms>;

/// The first of `frontiers`.
auto nearest_frontier( const frontier_options &opts ) -> std::optional<tripoint_bub_ms>;

/// Sets the auto-move route to the nearest frontier the pathfinder accepts. Returns false if none.
auto set_route_to_frontier( const frontier_options &opts ) -> bool;

/// The `auto_explore` action: refuses with hostiles in sight, otherwise starts walking.
auto handle( avatar &you ) -> void;

} // namespace auto_explore

#pragma once

#include <string>
#include <vector>

#include "color.h"
#include "point.h"

class avatar;

/// Arrows at the edge of the map for hostiles the player sees that are outside the
/// map window: one per compass direction, red when the hostile can reach the player
/// soon and yellow when it cannot. Arrows sit on the edge itself when the hostile is
/// hunting the player, one cell in when it is only trailing.
namespace enemy_indicators
{

/// Whether the arrows are on at all.
auto enabled() -> bool;

/// One arrow, placed `offset` cells from the player.
struct edge_arrow {
    point offset;
    std::string glyph;
    nc_color color;
};

/// The arrows for the hostiles the player sees outside a width x height window with
/// the player in the middle, worst directions first.
auto map_arrows( const avatar &you, int width, int height ) -> std::vector<edge_arrow>;

} // namespace enemy_indicators

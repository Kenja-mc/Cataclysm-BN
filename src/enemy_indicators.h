#pragma once

#include <string>
#include <vector>

#include "color.h"
#include "point.h"

class avatar;

namespace enemy_indicators
{

auto enabled() -> bool;

struct edge_arrow {
    point offset;
    std::string glyph;
    nc_color color;
};

auto map_arrows( avatar &you, int width, int height ) -> std::vector<edge_arrow>;

}

#pragma once

#include "color.h"
#include "coordinates.h"

class avatar;
class map;

namespace container_highlight
{

auto level( const avatar &you, const map &here, const tripoint_bub_ms &p ) -> int;
auto observe( avatar &you, const map &here ) -> void;
auto tint( int level ) -> nc_color;

}

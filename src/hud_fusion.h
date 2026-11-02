#pragma once

#include "point.h"

class avatar;

namespace catacurses
{
class window;
}

namespace hud_fusion
{

inline constexpr int status_rows = 5;
inline constexpr int loadout_rows = 4;
auto around_rows( const avatar &you ) -> int;

auto minimap_rows() -> int;

auto fits() -> bool;
auto active() -> bool;
auto draw( const avatar &you, const catacurses::window &w_terrain ) -> void;

auto clicked( avatar &you, const point &cell ) -> bool;

auto draw_minimap( avatar &you, const catacurses::window &w ) -> void;
auto draw_map_rule( avatar &you, const catacurses::window &w ) -> void;
auto draw_status( avatar &you, const catacurses::window &w ) -> void;
auto draw_loadout( avatar &you, const catacurses::window &w ) -> void;
auto draw_around( avatar &you, const catacurses::window &w ) -> void;
auto draw_log( avatar &you, const catacurses::window &w ) -> void;

}

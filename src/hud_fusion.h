#pragma once

#include "point.h"

class avatar;

namespace catacurses
{
class window;
} // namespace catacurses

/// The fusion HUD: a one-line ribbon at the top left and a LOADOUT deck over the map, beside the
/// "fusion" sidebar layout whose sections (status, map, body, around, log) open with a rule.
namespace hud_fusion
{

/// Rows the STATUS section needs, and the BODY and AROUND sections now: every limb is listed, and
/// AROUND grows with what is in sight.
inline constexpr int status_rows = 8;
auto body_rows( const avatar &you ) -> int;
auto around_rows( const avatar &you ) -> int;

/// Rows the pixel minimap takes: none when it is turned off, the player's own height when set,
/// otherwise a compact default so the log keeps the rest of the column.
auto minimap_rows() -> int;

/// The screen is large enough for the fusion layout; smaller screens fall back to "grouped".
auto fits() -> bool;
/// The fusion layout is selected and fits.
auto active() -> bool;
/// Paints the overlays over the map; call after the map window is refreshed.
auto draw( const avatar &you, const catacurses::window &w_terrain ) -> void;

/// Sidebar sections; each draws its rule on its first row.
/// A left click at a map-window cell: runs a hotbar slot, or is swallowed by an overlay.
auto clicked( avatar &you, const point &cell ) -> bool;

/// The pixel minimap, inset one column from the sidebar edge.
auto draw_minimap( avatar &you, const catacurses::window &w ) -> void;
auto draw_map_rule( avatar &you, const catacurses::window &w ) -> void;
auto draw_status( avatar &you, const catacurses::window &w ) -> void;
auto draw_body( avatar &you, const catacurses::window &w ) -> void;
auto draw_around( avatar &you, const catacurses::window &w ) -> void;
auto draw_log( avatar &you, const catacurses::window &w ) -> void;

} // namespace hud_fusion

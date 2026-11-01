#pragma once

#include <functional>
#include <string>
#include <utility>
#include <vector>

#include "color.h"
#include "point.h"

class avatar;
namespace catacurses
{
class window;
} // namespace catacurses

/// Minimizable, movable HUD windows over the map (issue #41).
namespace hud_windows
{

/// Per-character placement and visibility, saved with the avatar.
struct state {
    /// Top-left cell inside the map area, once the player has placed the window.
    point pos = point_zero;
    bool placed = false;
    bool collapsed = false;
    bool visible = true;
    /// Stacking order; a larger value draws above.  Raising a window sets it above all peers.
    int order = 0;
};

/// One body row a provider returns.
struct window_line {
    std::string icon;
    nc_color icon_color = c_light_gray;
    std::string text;
    nc_color text_color = c_light_gray;
};

/// Reading shown in the vehicle window.
struct vehicle_reading {
    /// False on foot, when there is no vehicle window to draw.
    bool applicable = false;
    std::string summary;
    std::vector<window_line> body;
    /// Fixed icon column, so rows with and without an icon keep their text aligned.  Zero
    /// makes each row's icon set its own prefix.
    int icon_width = 0;
};

/// Replacement for the vehicle window's reading, so the driving-dashboard design can take
/// the window over without touching its id, placement, collapse or save state.
using vehicle_provider = std::function<vehicle_reading( const avatar & )>;

/// Installs the vehicle reading provider. An empty provider restores the built-in reading.
auto set_vehicle_provider( vehicle_provider provider ) -> void;

/// On for the labels, labels-narrow and grouped layouts unless the option or compact corner
/// bars turn it off; classic and compact layouts keep their combined panels.
auto active() -> bool;

/// Draws every shown window.  Records their cells for mouse hit testing.
auto draw( const avatar &you, const catacurses::window &w ) -> void;

/// A left click in map-window cells.  Returns true when a window consumed it.
auto clicked( avatar &you, const catacurses::window &w, const point &map_cell ) -> bool;
/// A non-left click over a window: raises that window and consumes the click.
auto secondary_clicked( avatar &you, const catacurses::window &w, const point &map_cell ) -> bool;
/// Pointer motion while a window is being moved.  Returns true when it was consumed.
auto pointer_moved( avatar &you, const catacurses::window &w, const point &map_cell ) -> bool;
/// Drops a grabbed window without placing it, e.g. when the player presses a key.
auto release() -> void;

/// Stable id and translated name of every window, for the Sidebar Options menu.
auto entries() -> std::vector<std::pair<std::string, std::string>>;
/// Whether the window is enabled for this character; ignores being inapplicable.
auto visible( const avatar &you, const std::string &id ) -> bool;
/// Whether the window was actually drawn in the last frame.  A window that cannot fit the map
/// hands its reading back to the sidebar, so panel visibility follows this, not `visible`.
auto shown( const std::string &id ) -> bool;
/// Enables or disables a window from the Sidebar Options menu.
auto toggle( avatar &you, const std::string &id ) -> void;
/// Brings a window to the front of the stacking order (also reachable from Sidebar Options).
auto raise( avatar &you, const std::string &id ) -> void;

} // namespace hud_windows

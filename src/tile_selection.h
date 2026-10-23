#pragma once

#include <functional>
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

/// Same z, at most one step away, visible and not cut off by a turning vehicle.
auto reachable( const avatar &you, const tripoint_bub_ms &p ) -> bool;
/// What Space can do to a tile. A scan of the surroundings leaves out smashing ordinary
/// terrain and jumping over open ground, which only a tile the player picked offers.
auto interact_choices( const avatar &you, const tripoint_bub_ms &p,
                       bool explicit_tile ) -> std::vector<choice>;
/// Game actions on a tile that only `game` can run.
struct tile_actions {
    std::function<void( const tripoint_bub_ms & )> examine;
    std::function<void( const tripoint_bub_ms & )> pickup;
    std::function<void()> butcher;
    std::function<void( action_id )> vertical;
};
/// A picked tile: one safe action runs at once, several open a menu.
auto interact_at( avatar &you, const tripoint_bub_ms &p, const tile_actions &actions ) -> void;
/// Right click: always lists the tile's actions and never runs one. A tile out of reach lists
/// what it offers, disabled, with the reason. True when the player picked and ran an action.
auto interact_menu_at( avatar &you, const tripoint_bub_ms &p, const tile_actions &actions ) -> bool;
/// Every action on the surrounding tiles in one menu; false when there is none.
auto interact_nearby( avatar &you, const tile_actions &actions ) -> bool;
/// The action a left click on a tile takes without moving, if there is one.
auto primary_choice( const avatar &you, const tripoint_bub_ms &p ) -> std::optional<choice>;
/// A visible hostile stands on the tile.
auto has_hostile( const avatar &you, const tripoint_bub_ms &p ) -> bool;

auto hover( avatar &you, map &m, const std::optional<tripoint_bub_ms> &p ) -> void;
auto clear_hover() -> void;
auto hovered() -> std::optional<tripoint_bub_ms>;
auto hover_path() -> const std::vector<tripoint_bub_ms> &; // *NOPAD*
auto hint() -> std::string;

} // namespace tile_selection

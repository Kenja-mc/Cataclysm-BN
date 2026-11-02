#pragma once

#include <functional>
#include <optional>
#include <string>
#include <vector>

#include "action.h"
#include "coordinates.h"

class avatar;
class map;

namespace tile_selection
{

struct choice {
    action_id act = ACTION_NULL;
    std::string label;
    bool travel = false;
    bool vehicle_cargo = false;
};

auto enabled() -> bool;

auto choices_at( const avatar &you, const tripoint_bub_ms &p ) -> std::vector<choice>;
auto resolve( avatar &you, map &m, const choice &c, const tripoint_bub_ms &p ) -> action_id;

auto open_at( const tripoint_bub_ms &p ) -> void;
auto smash_at( const tripoint_bub_ms &p ) -> void;

auto reachable( const avatar &you, const tripoint_bub_ms &p ) -> bool;
auto interact_choices( const avatar &you, const tripoint_bub_ms &p,
                       bool explicit_tile ) -> std::vector<choice>;
struct tile_actions {
    std::function<void( const tripoint_bub_ms & )> examine;
    std::function<void( const tripoint_bub_ms & )> pickup;
    std::function<void( const tripoint_bub_ms & )> butcher;
    std::function<void( action_id )> vertical;
};
auto interact_at( avatar &you, const tripoint_bub_ms &p, const tile_actions &actions ) -> void;
auto toggle_curtain_at( avatar &you, const tripoint_bub_ms &p ) -> void;
auto toggle_curtain_nearby( avatar &you ) -> bool;
auto interact_menu_at( avatar &you, const tripoint_bub_ms &p, const tile_actions &actions ) -> bool;
auto interact_nearby( avatar &you, const tile_actions &actions ) -> bool;
auto primary_choice( const avatar &you, const tripoint_bub_ms &p ) -> std::optional<choice>;
auto has_hostile( const avatar &you, const tripoint_bub_ms &p ) -> bool;
auto smashable_at( const avatar &you, const tripoint_bub_ms &p ) -> bool;
auto corpse_at( const tripoint_bub_ms &p ) -> bool;
auto facing_tile( const avatar &you ) -> std::optional<tripoint_bub_ms>;

auto hover( avatar &you, map &m, const std::optional<tripoint_bub_ms> &p ) -> void;
auto clear_hover() -> void;
auto hovered() -> std::optional<tripoint_bub_ms>;
auto hover_path() -> const std::vector<tripoint_bub_ms> &; // *NOPAD*
auto hint() -> std::string;

}

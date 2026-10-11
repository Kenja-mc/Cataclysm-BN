#include "smart_safemode.h"

#include <algorithm>
#include <array>
#include <ranges>
#include <string_view>

#include "avatar.h"
#include "cached_options.h"
#include "game_constants.h"
#include "map/legacy_pathfinding.h"
#include "map/map.h"
#include "mattack_actors.h"
#include "monster.h"
#include "mtype.h"
#include "options.h"

namespace
{

/// Built-in special attacks that only hit an adjacent target.
constexpr auto adjacent_only = std::array<std::string_view, 2> { "GRAB", "GRAB_DRAG" };

/// Whether the attack can hurt someone it has no walking route to: turrets, spitters, leaps.
auto reaches_without_route( const mtype_special_attack &atk ) -> bool
{
    return dynamic_cast<const melee_actor *>( atk.get() ) == nullptr &&
           !std::ranges::contains( adjacent_only, std::string_view( atk->id ) );
}

} // namespace

namespace smart_safemode
{

auto threatens( const monster &mon, avatar &you ) -> bool
{
    if( !get_option<bool>( "SMART_SAFEMODE" ) ) {
        return true;
    }
    if( mon.is_fleeing( you ) ) {
        return false;
    }
    if( rl_dist( you.bub_pos(), mon.bub_pos() ) <= 1 ) {
        return true;
    }
    if( std::ranges::any_of( mon.type->special_attacks | std::views::values, reaches_without_route ) ) {
        return true;
    }
    if( mon.type->has_flag( MF_IMMOBILE ) || mon.type->speed <= 0 ) {
        return false;
    }
    const auto proximity = safe_mode_proximity <= 0 ? g_max_view_distance : safe_mode_proximity;
    const auto settings = pathfinding_settings{ 0, 2 * proximity, 4 * proximity, 0, false, false, true, false, false };
    return !get_map().route( mon.bub_pos(), you.bub_pos(), settings ).empty();
}

} // namespace smart_safemode

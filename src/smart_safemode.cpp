#include "smart_safemode.h"

#include <algorithm>
#include <array>
#include <functional>
#include <map>
#include <optional>
#include <ranges>
#include <string_view>
#include <tuple>
#include <vector>

#include "avatar.h"
#include "cached_options.h"
#include "calendar.h"
#include "coordinates.h"
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

/// One answer per monster and turn: the monster list, safe mode and the edge arrows ask
/// about the same monster within a turn, and a failed route search is slow.
struct reach_cache {
    time_point turn;
    std::map<std::tuple<const monster *, tripoint_bub_ms, tripoint_bub_ms,
        const pathfinding_settings *, int>, bool> answers;
};

auto cached_reach() -> reach_cache & // *NOPAD*
{
    static auto cache = reach_cache{};
    if( cache.turn != calendar::turn ) {
        cache = { .turn = calendar::turn, .answers = {} };
    }
    return cache;
}

auto route_reaches( const monster &mon, avatar &you, const int proximity ) -> bool
{
    auto &answers = cached_reach().answers;
    const auto &source_settings = mon.get_legacy_pathfinding_settings();
    const auto key = std::make_tuple( &mon, mon.bub_pos(), you.bub_pos(), &source_settings,
                                      proximity );
    if( const auto found = answers.find( key ); found != answers.end() ) {
        return found->second;
    }
    // The monster's own settings, so a zombie that can smash or open your door can reach you.
    auto settings = source_settings;
    settings.max_dist = 2 * proximity;
    settings.max_length = 4 * proximity;
    const auto reaches = !get_map().route( mon.bub_pos(), you.bub_pos(), settings ).empty();
    answers.emplace( key, reaches );
    return reaches;
}

auto proximity() -> int
{
    return safe_mode_proximity <= 0 ? g_max_view_distance : safe_mode_proximity;
}

/// The answer when no route search is needed, nullopt when only a route can tell.
auto answer_without_route( const monster &mon, avatar &you ) -> std::optional<bool>
{
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
    // map::route returns a clear straight line at any distance, so the distance cap goes first.
    if( rl_dist( you.bub_pos(), mon.bub_pos() ) > 2 * proximity() ) {
        return false;
    }
    return std::nullopt;
}

/// Bound route work without treating unexamined monsters as harmless.
constexpr auto max_route_searches = 12;

auto group_threatens( const auto &mons, avatar &you ) -> bool
{
    if( !get_option<bool>( "SMART_SAFEMODE" ) ) {
        return !mons.empty();
    }
    auto need_route = std::array<const monster *, max_route_searches> {};
    auto route_count = 0;
    auto unexamined = false;
    const auto distance = [&]( const monster * mon ) { return rl_dist( you.bub_pos(), mon->bub_pos() ); };
    for( const auto *mon : mons ) {
        const auto answer = answer_without_route( *mon, you );
        if( answer == true ) {
            return true;
        }
        if( answer ) {
            continue;
        }
        if( route_count < max_route_searches ) {
            need_route[route_count++] = mon;
        } else {
            unexamined = true;
            const auto farthest = std::ranges::max_element( need_route, std::less{}, distance );
            if( distance( mon ) < distance( *farthest ) ) {
                *farthest = mon;
            }
        }
    }
    const auto candidates = need_route | std::views::take( route_count );
    return std::ranges::any_of( candidates, [&]( const monster * mon ) {
        return route_reaches( *mon, you, proximity() );
    } ) || unexamined;
}

} // namespace

namespace smart_safemode
{

auto invalidate_reach_cache() -> void
{
    cached_reach().answers.clear();
}

auto threatens( const monster &mon, avatar &you ) -> bool
{
    return !get_option<bool>( "SMART_SAFEMODE" ) || can_reach_soon( mon, you );
}

auto can_reach_soon( const monster &mon, avatar &you ) -> bool
{
    const auto answer = answer_without_route( mon, you );
    return answer ? *answer : route_reaches( mon, you, proximity() );
}

auto any_threatens( const std::vector<const monster *> &mons, avatar &you ) -> bool
{
    return group_threatens( mons, you );
}

auto any_threatens( const std::vector<shared_ptr_fast<monster>> &mons, avatar &you ) -> bool
{
    const auto pointers = mons | std::views::transform( []( const auto & mon ) { return mon.get(); } );
    return group_threatens( pointers, you );
}

} // namespace smart_safemode

#include "auto_explore.h"

#include <vector>

#include "avatar.h"
#include "game_constants.h"
#include "map/map.h"
#include "messages.h"
#include "point.h"
#include "translations.h"
#include "trap.h"

namespace auto_explore
{
namespace
{

/// Tiles auto-explore will not step on: impassable (walls, closed doors), dangerous fields and
/// traps the player knows about.
auto blocked( map &here, const avatar &you, const tripoint_bub_ms &p ) -> bool
{
    if( !here.passable( p ) || here.dangerous_field_at( p ) ) {
        return true;
    }
    const auto &tr = here.tr_at( p );
    return !tr.is_null() && !tr.is_benign() && ( you.knows_trap( p ) || tr.can_see( p, you ) );
}

auto default_known( const avatar &you, const tripoint_bub_ms &p ) -> bool
{
    return you.sees( p ) || you.has_memorized_tile_for_autodrive( bub_to_abs( p ) );
}

} // namespace

auto frontiers( const frontier_options &opts, const size_t count ) -> std::vector<tripoint_bub_ms>
{
    auto &here = opts.here;
    const auto &you = opts.you;
    const auto known = [&]( const tripoint_bub_ms & p ) { return opts.is_known ? opts.is_known( p ) : default_known( you, p ); };

    const auto start = you.bub_pos();
    const auto side = 2 * opts.max_dist + 1;
    auto visited = std::vector<bool>( static_cast<size_t>( side * side ), false );
    const auto index = [&]( const tripoint_bub_ms & p ) { return static_cast<size_t>( ( p.y() - start.y() + opts.max_dist ) * side + ( p.x() - start.x() + opts.max_dist ) ); };

    // Plain BFS: with uniform step cost frontiers come out nearest first.
    auto found = std::vector<tripoint_bub_ms>();
    auto queue = std::vector<tripoint_bub_ms> { start };
    visited[index( start )] = true;
    for( auto head = size_t{ 0 }; head < queue.size() && found.size() < count; ++head ) {
        const auto cur = queue[head];
        auto touches_unknown = false;
        for( const tripoint &delta : eight_horizontal_neighbors ) {
            const auto next = cur + delta;
            if( !here.inbounds( next ) ) {
                continue;
            }
            touches_unknown = touches_unknown || !known( next );
            if( square_dist( start, next ) > opts.max_dist || visited[index( next )] ||
                !known( next ) || blocked( here, you, next ) ) {
                continue;
            }
            visited[index( next )] = true;
            queue.push_back( next );
        }
        if( touches_unknown && cur != start ) {
            found.push_back( cur );
        }
    }
    return found;
}

auto nearest_frontier( const frontier_options &opts ) -> std::optional<tripoint_bub_ms>
{
    const auto found = frontiers( opts, 1 );
    return found.empty() ? std::nullopt : std::optional( found.front() );
}

auto set_route_to_frontier( const frontier_options &opts ) -> bool
{
    auto &you = opts.you;
    // The pathfinder can refuse a frontier the flood fill reached (e.g. a tile it avoids), so
    // fall back to the next nearest ones.
    constexpr auto attempts = size_t{ 8 };
    for( const auto &target : frontiers( opts, attempts ) ) {
        const auto route = opts.here.route( you.bub_pos(), target, you.get_legacy_pathfinding_settings(),
                                            you.get_legacy_path_avoid() );
        if( !route.empty() ) {
            // The main loop takes the steps; consuming one here would desync next_expected_position.
            you.set_destination( route );
            return true;
        }
    }
    return false;
}

auto handle( avatar &you ) -> void
{
    if( !you.get_hostile_creatures( g_max_view_distance ).empty() ) {
        add_msg( m_info, _( "You can't explore with enemies in sight." ) );
        return;
    }
    if( !set_route_to_frontier( { .you = you, .here = get_map() } ) ) {
        add_msg( m_info, _( "Nothing left to explore nearby." ) );
    }
}

} // namespace auto_explore

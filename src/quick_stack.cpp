#include "quick_stack.h"

#include <algorithm>
#include <map>
#include <optional>
#include <ranges>
#include <set>
#include <vector>

#include "action.h"
#include "activity_handlers.h"
#include "avatar.h"
#include "cached_options.h"
#include "calendar.h"
#include "item.h"
#include "item_category.h"
#include "line.h"
#include "map/map.h"
#include "messages.h"
#include "string_formatter.h"
#include "translations.h"
#include "vehicle/vehicle.h"
#include "vehicle/vpart_position.h"

namespace quick_stack
{
namespace
{

struct spot {
    tripoint_bub_ms pos = {};
    bool is_storage = false;
    int dist = 0;
    std::set<itype_id> types = {};
    std::map<item_category_id, int> categories = {};
    int total = 0;
    std::vector<detached_ptr<item>> incoming = {};
};

struct move_plan {
    item *it = nullptr;
    size_t spot_index = 0;
};

auto record( spot &s, const item &it ) -> void
{
    s.types.insert( it.typeId() );
    s.categories[it.get_category().get_id()]++;
    s.total++;
}

auto dominant_category( const spot &s ) -> std::optional<item_category_id>
{
    const auto best = std::ranges::max_element( s.categories, {}, &std::pair<const item_category_id, int>::second );
    if( best == s.categories.end() || best->second * 2 <= s.total ) {
        return std::nullopt;
    }
    return best->first;
}

/// Every visible tile in crafting range that already holds items or is furniture/vehicle storage.
auto gather_spots( avatar &you, const std::optional<tripoint_bub_ms> &skip ) -> std::vector<spot>
{
    auto &here = get_map();
    auto spots = std::vector<spot>();
    for( const auto &p : here.points_in_radius( you.bub_pos(), PICKUP_RANGE ) ) {
        if( p == skip || !you.sees( p ) || here.has_flag( "SEALED", p ) ) {
            continue;
        }
        auto s = spot{ .pos = p, .dist = rl_dist( you.bub_pos(), p ) };
        if( const auto vp = here.veh_at( p ).part_with_feature( "CARGO", false ) ) {
            s.is_storage = true;
            for( const item *it : vp->vehicle().get_items( vp->part_index() ) ) {
                record( s, *it );
            }
        } else {
            if( !here.can_put_items( p ) ) {
                continue;
            }
            s.is_storage = here.has_flag_furn( "CONTAINER", p ) || here.has_flag_furn( "PLACE_ITEM", p );
            for( const item *it : here.i_at( p ) ) {
                record( s, *it );
            }
        }
        if( s.total > 0 || s.is_storage ) {
            spots.push_back( std::move( s ) );
        }
    }
    return spots;
}

/// Same item anywhere beats same category; storage beats loose piles; closer beats farther.
auto pick_spot( const std::vector<spot> &spots, const item &it ) -> std::optional<size_t>
{
    auto best = std::optional<size_t>();
    auto best_score = 0;
    for( size_t i = 0; i < spots.size(); i++ ) {
        const auto &s = spots[i];
        auto score = 0;
        if( s.types.contains( it.typeId() ) ) {
            score = 3000;
        } else if( dominant_category( s ) == it.get_category().get_id() ) {
            score = 2000;
        } else {
            continue;
        }
        score += ( s.is_storage ? 500 : 0 ) - s.dist;
        if( score > best_score ) {
            best = i;
            best_score = score;
        }
    }
    return best;
}

auto plan_moves( std::vector<spot> &spots, const std::vector<item *> &items ) -> std::vector<move_plan>
{
    auto plan = std::vector<move_plan>();
    for( item *it : items ) {
        if( const auto idx = pick_spot( spots, *it ) ) {
            plan.push_back( { .it = it, .spot_index = *idx } );
            record( spots[*idx], *it );
        }
    }
    return plan;
}

template<typename Detach>
auto execute( avatar &you, std::vector<spot> &spots, const std::vector<move_plan> &plan,
              Detach detach ) -> void
{
    auto moves = 0;
    for( const auto &mv : plan ) {
        moves += you.item_handling_cost( *mv.it, true, 50 );
        spots[mv.spot_index].incoming.push_back( detach( mv.it ) );
    }
    auto visited = 0;
    for( auto &s : spots ) {
        if( s.incoming.empty() ) {
            continue;
        }
        visited++;
        // Walking over and back, minus the step we would be adjacent anyway.
        moves += std::max( 0, s.dist - 1 ) * 2 * 100;
        put_into_vehicle_or_drop( you, item_drop_reason::deliberate, s.incoming, s.pos );
    }
    you.mod_moves( -moves );
    add_msg( m_good, vgettext( "Stashed %1$d item into %2$d spot (%3$s).",
                               "Stashed %1$d items into %2$d spots (%3$s).", plan.size() ),
             plan.size(), visited, to_string( time_duration::from_turns( moves / 100 + 1 ) ) );
}

} // namespace

auto stash_inventory( avatar &you ) -> void
{
    auto carried = you.inv_dump()
                   | std::views::filter( [&]( const item * it ) { return !you.is_worn( *it ) && !you.is_wielding( *it ); } )
                   | std::views::filter( []( const item * it ) { return !it->is_favorite; } )
                   | std::ranges::to<std::vector>();
    if( carried.empty() ) {
        add_msg( m_info, _( "Nothing to stash.  Worn, wielded and favorite (*) items always stay with you." ) );
        return;
    }
    auto spots = gather_spots( you, std::nullopt );
    const auto plan = plan_moves( spots, carried );
    if( plan.empty() ) {
        add_msg( m_info, _( "No nearby storage holds anything like what you carry.  Drop your haul, stand on it and %s to sort it." ),
                 press_x( ACTION_SORT_PILE ) );
        return;
    }
    execute( you, spots, plan, [&]( item * it ) { return you.inv_remove_item( it ); } );
}

auto sort_pile( avatar &you ) -> void
{
    auto &here = get_map();
    const auto feet = you.bub_pos();
    auto pile = std::vector<item *>();
    for( item *it : here.i_at( feet ) ) {
        pile.push_back( it );
    }
    if( pile.empty() ) {
        add_msg( m_info, _( "There's nothing here to sort.  Stand on a pile first." ) );
        return;
    }
    auto spots = gather_spots( you, feet );
    const auto plan = plan_moves( spots, pile );
    if( plan.empty() ) {
        add_msg( m_info, _( "Nothing nearby matches this pile.  Put one of each kind of thing where you want it to live." ) );
        return;
    }
    execute( you, spots, plan, [&]( item * it ) { return here.i_at( feet ).remove( it ); } );
}

} // namespace quick_stack

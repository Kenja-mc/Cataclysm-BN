#include "combine_items.h"

#include <algorithm>
#include <ranges>
#include <vector>

#include "ammo.h"
#include "avatar.h"
#include "item.h"
#include "item_variant.h"
#include "itype.h"
#include "messages.h"
#include "stack_modifier.h"
#include "string_formatter.h"
#include "translations.h"

namespace
{

constexpr auto moves_per_item = 50;

/// Same tool, ignoring charges: cosmetic variants mix, other variants must match.
auto same_kind( const item &a, const item &b ) -> bool
{
    if( a.typeId() != b.typeId() ) {
        return false;
    }
    if( item_variants::cosmetic( *a.type ) ) {
        return true;
    }
    const auto va = item_variants::of( a );
    const auto vb = item_variants::of( b );
    return va && vb ? va->id == vb->id : static_cast<bool>( va ) == static_cast<bool>( vb );
}

} // namespace

namespace combine_items
{

auto is_eligible( const item &it ) -> bool
{
    if( !it.is_tool() || it.count_by_charges() ) {
        return false;
    }
    const auto max = it.type->tool->max_charges;
    if( max <= 0 || it.charges <= 0 || it.charges >= max ) {
        return false;
    }
    // Tools fed by another item (fuel, batteries) refill from that instead.
    return !it.ammo_type() || it.ammo_type()->default_ammotype() == it.typeId();
}

auto partners( const avatar &you, const item &target ) -> std::vector<item *>
{
    using namespace std::views;
    return you.all_items()
           | filter( [&]( const item * it ) { return it != &target && is_eligible( *it ) && same_kind( target, *it ); } )
           | std::ranges::to<std::vector>();
}

auto combine( avatar &you, item &target ) -> void
{
    if( !is_eligible( target ) ) {
        return;
    }
    auto sources = partners( you, target );
    if( sources.empty() ) {
        add_msg( m_info, _( "You have no other partly used %s." ), target.tname( 1, false ) );
        return;
    }
    // Emptiest first, so the fewest items are left over.
    std::ranges::sort( sources, {}, &item::charges );

    const auto max = target.type->tool->max_charges;
    auto emptied = 0;
    for( auto *source : sources ) {
        const auto take = std::min( max - target.charges, source->charges );
        if( take <= 0 ) {
            break;
        }
        stack_modifiers::transfer( *source, target, take );
        source->charges -= take;
        target.charges += take;
        if( source->charges == 0 ) {
            source->detach();
            emptied++;
        }
    }
    you.mod_moves( -moves_per_item * std::max( emptied, 1 ) );
    if( emptied == 0 ) {
        add_msg( m_good, _( "You top up the %s." ), target.tname( 1, false ) );
        return;
    }
    add_msg( m_good, vgettext( "You combine %1$d %2$s into one.", "You combine %1$d %2$s into one.",
                               emptied + 1 ), emptied + 1, target.tname( emptied + 1, false ) );
}

} // namespace combine_items

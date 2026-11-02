#include "hotbar.h"

#include <string>
#include <vector>

#include "action.h"
#include "avatar.h"
#include "avatar_action.h"
#include "avatar_functions.h"
#include "game_inventory.h"
#include "input.h"
#include "item.h"
#include "itype.h"
#include "messages.h"
#include "translations.h"
#include "type_id.h"
#include "ui.h"

namespace hotbar
{

namespace
{

auto key_of( const int slot ) -> std::string { return "hotbar_" + std::to_string( slot + 1 ); }

auto assigned_type( const avatar &you, const int slot ) -> itype_id
{
    return itype_id( you.get_value( key_of( slot ) ) );
}

auto find( avatar &you, const itype_id &type ) -> item *
{
    auto *found = static_cast<item *>( nullptr );
    for( item *it : you.all_items( false ) ) {
        if( it->typeId() != type ) {
            continue;
        }
        if( you.is_wielding( *it ) ) {
            return it;
        }
        if( found == nullptr ) {
            found = it;
        }
    }
    return found;
}

}

auto view( const avatar &you, const int slot ) -> slot_view
{
    auto out = slot_view();
    const auto type = assigned_type( you, slot );
    if( type.is_empty() || !type.is_valid() ) {
        return out;
    }
    const auto &proto = *type;
    out.assigned = true;
    out.symbol = proto.sym;
    out.color = proto.color;
    out.name = proto.nname( 1 );
    for( const item *it : you.all_items( false ) ) {
        if( it->typeId() != type ) {
            continue;
        }
        out.count += it->count_by_charges() ? it->charges : 1;
        out.wielded = out.wielded || you.is_wielding( *it );
    }
    return out;
}

auto use_item( avatar &you, item *loc ) -> void
{
    if( loc->is_book() ) {
        you.read( loc );
    } else if( loc->is_comestible() ) {
        avatar_action::eat( you, loc );
    } else if( loc->is_gun() && you.is_wielding( *loc ) && loc->ammo_remaining() > 0 ) {
        avatar_action::unload( you );
    } else if( loc->is_gun() || loc->is_melee() ) {
        avatar_action::wield( *loc );
    } else if( loc->is_armor() ) {
        loc->obtain( you );
        you.wear_possessed( *loc );
    } else {
        avatar_funcs::use_item( you, *loc );
    }
}

auto use( avatar &you, const int slot ) -> void
{
    const auto type = assigned_type( you, slot );
    if( type.is_empty() || !type.is_valid() ) {
        const auto letter = static_cast<char>( '1' + slot );
        for( item *it : you.all_items( false ) ) {
            if( it->invlet == letter ) {
                use_item( you, it );
                return;
            }
        }
        add_msg( m_info, _( "Hotbar slot %d is empty.  Assign an item to it from the hotbar menu." ),
                 slot + 1 );
        return;
    }
    auto *const it = find( you, type );
    if( it == nullptr ) {
        add_msg( m_info, _( "You have no %s for hotbar slot %d." ), type->nname( 1 ), slot + 1 );
        return;
    }
    if( it->is_gun() && you.is_wielding( *it ) ) {
        if( it->ammo_remaining() < it->ammo_capacity() ) {
            avatar_action::reload_wielded();
        } else {
            add_msg( m_info, _( "Your %s is already loaded." ), it->tname() );
        }
        return;
    }
    if( you.is_wielding( *it ) && ( it->is_melee() || !it->is_comestible() ) && !it->is_tool() ) {
        add_msg( m_info, _( "You already wield your %s." ), it->tname() );
        return;
    }
    use_item( you, it );
}

auto assign( avatar &you ) -> void
{
    auto menu = uilist();
    menu.title = _( "Assign which hotbar slot?" );
    for( auto i = 0; i < slots; ++i ) {
        const auto v = view( you, i );
        menu.addentry( i, true, '1' + i,
                       string_format( "%d  %s", i + 1, v.assigned ? v.name : std::string( _( "(empty)" ) ) ) );
    }
    menu.query();
    if( menu.ret < 0 ) {
        return;
    }
    const auto slot = menu.ret;
    item *const chosen = game_menus::inv::titled_menu( you,
                         _( "Put which item in the slot?  (Esc clears it)" ) );
    if( chosen == nullptr ) {
        you.set_value( key_of( slot ), "" );
        add_msg( m_info, _( "Hotbar slot %d cleared." ), slot + 1 );
        return;
    }
    you.set_value( key_of( slot ), chosen->typeId().str() );
    add_msg( m_info, _( "Hotbar slot %d: %s." ), slot + 1, chosen->type_name( 1 ) );
}

}

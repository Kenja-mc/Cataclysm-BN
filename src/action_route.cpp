#include "action_route.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "input.h"
#include "options.h"
#include "string_formatter.h"
#include "translations.h"

namespace
{

/// The item panel button that does the action, for actions done on a carried item.
auto item_panel_action( const action_id act ) -> std::optional<std::string>
{
    switch( act ) {
    case ACTION_WIELD:
        return "WIELD";
    case ACTION_WEAR:
        return "WEAR";
    case ACTION_TAKE_OFF:
        return "TAKE_OFF";
    case ACTION_EAT:
        return "EAT";
    case ACTION_USE:
        return "ACTIVATE";
    case ACTION_DROP:
        return "DROP";
    case ACTION_UNLOAD:
        return "UNLOAD";
    case ACTION_READ:
        return "READ";
    case ACTION_THROW:
        return "THROW";
    default:
        return std::nullopt;
}
}

/// Space acts on the surrounding tiles when contextual interaction is on.
auto contextual( const action_id act ) -> bool
{
    switch( act ) {
    case ACTION_OPEN:
    case ACTION_CLOSE:
    case ACTION_SMASH:
    case ACTION_PICKUP:
    case ACTION_EXAMINE:
    case ACTION_JUMP:
        return true;
    default:
        return false;
}
}

/// The action menu category an action sits in; mirrors handle_action_menu.
auto menu_category( const action_id act ) -> std::optional<std::string>
{
    switch( act ) {
    case ACTION_LOOK:
    case ACTION_PEEK:
    case ACTION_CENTER:
    case ACTION_LIST_ITEMS:
    case ACTION_ZONES:
    case ACTION_MAP:
    case ACTION_SKY:
        return _( "Look" );
        case ACTION_INVENTORY:
        case ACTION_ADVANCEDINV:
        case ACTION_SORT_ARMOR:
        case ACTION_DIR_DROP:
        case ACTION_COMPARE:
        case ACTION_ORGANIZE:
        case ACTION_USE_WIELDED:
        case ACTION_OPEN_CONSUME:
        case ACTION_UNLOAD_ALL:
            return _( "Inventory" );
        case ACTION_OPEN:
        case ACTION_CLOSE:
        case ACTION_SMASH:
        case ACTION_EXAMINE:
        case ACTION_JUMP:
        case ACTION_PICKUP:
        case ACTION_CHAT:
        case ACTION_PICKUP_ALL:
        case ACTION_PICKUP_FEET:
        case ACTION_GRAB:
        case ACTION_HAUL:
        case ACTION_BUTCHER:
        case ACTION_LOOT:
        case ACTION_QUICK_STACK:
        case ACTION_SORT_PILE:
        case ACTION_AUTO_EXPLORE:
        case ACTION_ATTACK:
            return _( "Interact" );
        case ACTION_CYCLE_MOVE:
        case ACTION_RESET_MOVE:
        case ACTION_TOGGLE_RUN:
        case ACTION_TOGGLE_CROUCH:
        case ACTION_TOGGLE_PRONE:
        case ACTION_OPEN_MOVEMENT:
        case ACTION_AUTOATTACK:
        case ACTION_FIRE:
        case ACTION_RELOAD_ITEM:
        case ACTION_RELOAD_WEAPON:
        case ACTION_RELOAD_WIELDED:
        case ACTION_CAST_SPELL:
        case ACTION_CAST_LAST_SPELL:
        case ACTION_SELECT_FIRE_MODE:
        case ACTION_SELECT_DEFAULT_AMMO:
        case ACTION_FIRE_BURST:
        case ACTION_PICK_STYLE:
            return _( "Combat" );
        case ACTION_CRAFT:
        case ACTION_RECRAFT:
        case ACTION_LONGCRAFT:
        case ACTION_CONSTRUCT:
        case ACTION_DISASSEMBLE:
        case ACTION_SALVAGE:
            return _( "Craft" );
        case ACTION_PL_INFO:
        case ACTION_BODY_STATUS:
        case ACTION_MISSIONS:
        case ACTION_SCORES:
        case ACTION_FACTIONS:
        case ACTION_MORALE:
        case ACTION_MESSAGES:
        case ACTION_DIARY:
            return _( "Info" );
        case ACTION_WAIT:
        case ACTION_SLEEP:
        case ACTION_BIONICS:
        case ACTION_MUTATIONS:
        case ACTION_PERKS:
        case ACTION_CONTROL_VEHICLE:
        case ACTION_ITEMACTION:
        case ACTION_TOGGLE_PANEL_ADM:
        case ACTION_TOGGLE_THIEF_MODE:
        case ACTION_SOUND_MENU:
            return _( "Misc" );
        default:
            return std::nullopt;
    }
}

auto bound_key( const action_id act ) -> std::string
{
    const auto keys = keys_bound_to( act );
    if( keys.empty() ) {
        return press_x( act, "", "" );
    }
    // One key reads better than every binding ("w", not "w or UP or 8 or NUMPAD_8").
    return keys.front() == ' ' ? std::string( _( "Space" ) ) : std::string( 1, keys.front() );
}

/// How the Modern scheme selects a tile: its directional selection keys.  They read as
/// "Shift + a movement key" only while they really are the shifted movement keys.
auto look_selection_route() -> std::optional<std::string>
{
    static const auto directions = std::array{
        std::pair{ "shift_n", "UP" }, std::pair{ "shift_ne", "RIGHTUP" },
        std::pair{ "shift_e", "RIGHT" }, std::pair{ "shift_se", "RIGHTDOWN" },
        std::pair{ "shift_s", "DOWN" }, std::pair{ "shift_sw", "LEFTDOWN" },
        std::pair{ "shift_w", "LEFT" }, std::pair{ "shift_nw", "LEFTUP" },
    };
    auto ctxt = input_context( "DEFAULTMODE" );
    auto keys = std::vector<char>();
    auto all_shifted_movement = true;
    for( const auto &[selection, movement] : directions ) {
        const auto selection_keys = ctxt.keys_bound_to( selection );
        if( selection_keys.empty() ) {
            all_shifted_movement = false;
            continue;
        }
        const auto movement_keys = ctxt.keys_bound_to( movement );
        for( const auto key : selection_keys ) {
            keys.push_back( key );
            const auto lower = static_cast<char>(
                                   std::tolower( static_cast<unsigned char>( key ) ) );
            if( key != lower || !std::ranges::contains( movement_keys, lower ) ) {
                all_shifted_movement = false;
            }
        }
    }
    if( keys.empty() ) {
        return std::nullopt;
    }
    if( all_shifted_movement ) {
        return std::string( _( "Shift + a movement key" ) );
    }
    auto out = std::string();
    auto seen = std::vector<char>();
    for( const auto key : keys ) {
        if( std::ranges::contains( seen, key ) ) {
            continue;
        }
        seen.push_back( key );
        if( !out.empty() ) {
            out += ", ";
        }
        out += key == ' ' ? std::string( _( "Space" ) ) : std::string( 1, key );
    }
    return out;
}

} // namespace

auto action_route( const action_id act ) -> std::string
{
    if( act == ACTION_NULL ) {
        return std::string();
    }
    if( const auto key = bound_key( act ); !key.empty() ) {
        return key;
    }
    if( contextual( act ) && get_option<bool>( "CONTEXTUAL_INTERACT" ) ) {
        if( const auto interact = bound_key( ACTION_EXAMINE ); !interact.empty() ) {
            return interact;
        }
    }
    if( act == ACTION_LOOK && get_option<std::string>( "CONTROL_SCHEME" ) == "modern" ) {
        if( const auto route = look_selection_route() ) {
            return *route;
        }
    }
    const auto inventory = bound_key( ACTION_INVENTORY );
    if( const auto button = item_panel_action( act ); button && !inventory.empty() ) {
        //~ How to reach an item action: inventory key, the item, then the button, e.g. "i → item → Wield".
        return string_format( _( "%1$s → item → %2$s" ), inventory,
                              input_context( "INVENTORY_ITEM" ).get_action_name( *button ) );
    }
    const auto menu = bound_key( ACTION_ACTIONMENU );
    if( const auto category = menu_category( act ); category && !menu.empty() ) {
        //~ How to reach an action through the action menu, e.g. "RETURN → Info → View player info".
        return string_format( _( "%1$s → %2$s → %3$s" ), menu, *category,
                              input_context( "DEFAULTMODE" ).get_action_name( action_ident( act ) ) );
    }
    return _( "(unbound)" );
}

auto action_route( const std::string &id ) -> std::string
{
    if( const auto act = look_up_action( id ); act != ACTION_NULL ) {
        return action_route( act );
    }
    // Target cycling ids (NEXT_TARGET, PREV_TARGET) are only bound in the aiming context.
    if( inp_mngr.get_input_for_action( id, "DEFAULTMODE" ).empty() &&
        !inp_mngr.get_input_for_action( id, "TARGET" ).empty() ) {
        return input_context( "TARGET" ).get_desc( id, 1 );
    }
    return input_context( "DEFAULTMODE" ).get_desc( id, 1 );
}

auto action_route( const std::string &id, const std::string &context ) -> std::string
{
    if( context.empty() || context == "DEFAULTMODE" ) {
        return action_route( id );
    }
    // The input manager already falls back to the binding the context would really use.
    // A context without one keeps the old default-mode route instead of inventing a key.
    if( !inp_mngr.get_input_for_action( id, context ).empty() ) {
        return input_context( context ).get_desc( id, 1 );
    }
    return action_route( id );
}

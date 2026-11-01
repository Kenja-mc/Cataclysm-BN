#include "keyhints_panel.h"

#include <algorithm>
#include <array>
#include <string>
#include <vector>

#include "action.h"
#include "action_route.h"
#include "avatar.h"
#include "catacharset.h"
#include "color.h"
#include "cursesdef.h"
#include "game.h"
#include "input.h"
#include "init.h"
#include "options.h"
#include "output.h"
#include "panels.h"
#include "string_formatter.h"
#include "translations.h"
#include "ui.h"

namespace
{

struct hint {
    std::string keys;
    std::string label;
    int keys_width;
    int label_width;
};

auto key_name( const char ch ) -> std::string
{
    return ch == ' ' ? std::string( _( "spc" ) ) : std::string( 1, ch );
}

auto first_key( const action_id act ) -> std::string
{
    const auto ctxt = input_context( "DEFAULTMODE" );
    if( ctxt.key_bound_to( action_ident( act ), 0, false ).empty() ) {
        return {};
    }
    const auto desc = ctxt.get_desc( action_ident( act ), 1 );
    return desc == inp_mngr.get_keyname( ' ', input_event_t::keyboard ) ? key_name( ' ' ) : desc;
}

auto joined_keys( const std::vector<action_id> &acts ) -> std::string
{
    auto out = std::string();
    for( const auto act : acts ) {
        out += first_key( act );
    }
    return out;
}

/// "CTRL+WASD" when the four peek directions share a modifier, else the north peek key.
auto peek_keys( const input_context &ctxt ) -> std::string
{
    constexpr auto ids = std::array{ "PEEK_N", "PEEK_W", "PEEK_S", "PEEK_E" };
    if( std::ranges::any_of( ids, [&]( const char *id ) { return ctxt.key_bound_to( id, 0, false ).empty(); } ) ) {
        return std::string();
    }
    auto prefix = std::string();
    auto letters = std::string();
    for( const auto *id : ids ) {
        const auto desc = ctxt.get_desc( id, 1 );
        const auto plus = desc.rfind( '+' );
        if( plus == std::string::npos || plus + 2 != desc.size() ||
            ( !prefix.empty() && desc.substr( 0, plus + 1 ) != prefix ) ) {
            return ctxt.get_desc( "PEEK_N", 1 );
        }
        prefix = desc.substr( 0, plus + 1 );
        letters += desc.back();
    }
    return prefix + letters;
}

auto collect_hints( const bool driving ) -> std::vector<hint>
{
    const auto modern = get_option<std::string>( "CONTROL_SCHEME" ) == "modern";
    const auto everyday = std::vector<std::pair<action_id, std::string>> {
        { ACTION_EXAMINE, _( "interact" ) }, { ACTION_INVENTORY, _( "inventory" ) },
        { ACTION_ACTIONMENU, _( "menus" ) }, { ACTION_USE_CONTEXTUAL, _( "use" ) },
        { ACTION_USE, _( "use" ) }, { ACTION_WIELD, _( "wield" ) },
        { ACTION_FIRE, modern ? _( "attack" ) : _( "fire" ) }, { ACTION_AUTOATTACK, _( "attack" ) },
        { ACTION_PICKUP, _( "pick up" ) }, { ACTION_PAUSE, _( "wait" ) }, { ACTION_MAP, _( "map" ) },
        { ACTION_WORLD_HUB, _( "world" ) }, { ACTION_BODY_STATUS, _( "health" ) },
        { ACTION_PICKUP_LIST, _( "pickup list" ) }, { ACTION_RELOAD_ITEM, _( "reload" ) },
        { ACTION_CRAFT, _( "craft" ) }, { ACTION_AUTO_EXPLORE, _( "explore" ) },
        { ACTION_SEARCH_ACTION, _( "find action" ) },
    };
    // Toggles and base-keeping come after the keys a new player needs to act at all.
    const auto later = std::vector<std::pair<action_id, std::string>> {
        { ACTION_TOGGLE_SAFEMODE, _( "safe mode" ) }, { ACTION_TOGGLE_AUTO_TRAVEL_MODE, _( "auto travel" ) },
        { ACTION_QUICK_STACK, _( "stash" ) }, { ACTION_SORT_PILE, _( "sort pile" ) },
        // Look goes last: it is the first to drop off a full strip, and hovering the map covers it.
        { ACTION_TOGGLE_PANEL_ADM, _( "sidebar" ) }, { ACTION_LOOK, _( "look" ) },
    };
    auto hints = std::vector<hint>();
    hints.reserve( everyday.size() + later.size() + 8 );
    auto push = [&]( std::string keys, std::string label ) {
        if( keys.empty() ) {
            // An unbound hint would print get_desc()'s "Unbound globally!" text as if it were keys.
            return;
        }
        hint h;
        h.keys = std::move( keys );
        h.label = std::move( label );
        h.keys_width = utf8_width( h.keys );
        h.label_width = utf8_width( h.label );
        hints.push_back( std::move( h ) );
    };
    const auto push_all = [&]( const std::vector<std::pair<action_id, std::string>> &acts ) {
        for( const auto &[act, label] : acts ) {
            push( first_key( act ), label );
        }
    };
    if( driving ) {
        push( joined_keys( { ACTION_MOVE_FORTH, ACTION_MOVE_BACK } ), _( "throttle" ) );
        push( joined_keys( { ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT } ), _( "steer" ) );
    } else {
        push( joined_keys( { ACTION_MOVE_FORTH, ACTION_MOVE_LEFT, ACTION_MOVE_BACK, ACTION_MOVE_RIGHT } ),
              _( "move" ) );
        push( joined_keys( { ACTION_MOVE_FORTH_LEFT, ACTION_MOVE_FORTH_RIGHT, ACTION_MOVE_BACK_LEFT, ACTION_MOVE_BACK_RIGHT } ),
              _( "diag" ) );
    }
    // The key list fits one row beside move and diag, so it survives the tightest strip.
    push( first_key( ACTION_KEYBINDINGS ), _( "all keys" ) );
    push_all( everyday );
    if( modern ) {
        const auto ctxt = input_context( "DEFAULTMODE" );
        if( !ctxt.key_bound_to( "NEXT_TARGET", 0, false ).empty() ) {
            push( ctxt.get_desc( "NEXT_TARGET", 1 ), _( "target" ) );
        }
        push( first_key( ACTION_CYCLE_MOVE ), _( "stance" ) );
        // Shift+direction moves the selection marker; calling it "look" made it read like peeking.
        push( joined_keys( { ACTION_SHIFT_N, ACTION_SHIFT_W, ACTION_SHIFT_S, ACTION_SHIFT_E } ),
              _( "select" ) );
        push( peek_keys( ctxt ), _( "peek" ) );
    }
    push_all( later );
    return hints;
}

auto menu_context() -> const input_context * // *NOPAD*
{
    const auto *ctxt = input_context::get_active();
    return get_option<bool>( "CONTEXT_KEYHINTS" ) && ctxt &&
           ctxt->get_category() != "DEFAULTMODE" ? ctxt : nullptr;
}

auto collect_menu_hints( const input_context &ctxt ) -> std::vector<hint>
{
    constexpr auto internal = std::array{ "ANY_INPUT", "COORDINATE", "MOUSE_MOVE", "SELECT",
                                          "SEC_SELECT", "HELP_KEYBINDINGS", "TIMEOUT", "ERROR" };
    constexpr auto priority = std::array{ "CRAFT", "SELECT_ALL", "CYCLE_BATCH", "FIRE", "CENTER",
                                          "CONFIRM", "QUIT", "FILTER", "INVENTORY_FILTER", "UP", "DOWN",
                                          "LEFT", "RIGHT", "WIELD", "WEAR" };
    auto actions = std::vector<std::string>();
    for( const auto &action : ctxt.get_registered_actions() ) {
        if( std::ranges::find( internal, action ) == internal.end() &&
            !action.starts_with( "debug_" ) && !action.starts_with( "TEXT." ) &&
            !ctxt.key_bound_to( action, 0, false ).empty() ) {
            actions.push_back( action );
        }
    }
    const auto rank = [&]( const std::string & action ) {
        return std::ranges::find( priority, action ) - priority.begin();
    };
    std::ranges::stable_sort( actions, [&]( const auto & a, const auto & b ) {
        return rank( a ) < rank( b );
    } );
    auto hints = std::vector<hint>();
    hints.reserve( actions.size() );
    const auto keyboard = []( const input_event & event ) {
        return event.type == input_event_t::keyboard;
    };
    for( const auto &action : actions ) {
        auto keys = ctxt.get_desc( action, 1, keyboard );
        auto label = remove_color_tags( ctxt.get_action_name( action ) );
        const auto keys_width = utf8_width( keys );
        const auto label_width = utf8_width( label );
        hints.push_back( hint{ .keys = std::move( keys ), .label = std::move( label ),
                               .keys_width = keys_width, .label_width = label_width } );
    }
    return hints;
}

auto cached_hints( const bool driving ) -> const std::vector<hint> & // *NOPAD*
{
    static auto cached = std::vector<hint>();
    static auto cached_version = -1;
    static auto cached_context = size_t{ 0 };
    static auto cached_driving = false;
    const auto *ctxt = menu_context();
    const auto context = ctxt ? input_context::active_context_version() : 0;
    if( cached_version != inp_mngr.bindings_version() || cached_context != context ||
        cached_driving != driving ) {
        cached = ctxt ? collect_menu_hints( *ctxt ) : collect_hints( driving );
        cached_version = inp_mngr.bindings_version();
        cached_context = context;
        cached_driving = driving;
    }
    return cached;
}

auto draw_hints( const catacurses::window &w, const std::vector<hint> &hints,
                 const point start ) -> void
{
    const auto width = getmaxx( w ) - 1;
    const auto height = getmaxy( w );
    auto pos = start;
    for( const auto &h : hints ) {
        const auto len = h.keys_width + 1 + h.label_width;
        if( len > width - start.x ) {
            continue;
        }
        if( pos.x > start.x && pos.x + len > width ) {
            pos = point( start.x, pos.y + 1 );
        }
        if( pos.y >= height ) {
            break;
        }
        mvwprintz( w, pos, c_light_cyan, h.keys );
        mvwprintz( w, pos + point( h.keys_width + 1, 0 ), c_dark_gray, h.label );
        pos.x += len + 2;
    }
}

} // namespace

auto draw_keyhints( const avatar &you, const catacurses::window &w ) -> void
{
    werase( w );
    const auto driving = you.controlling_vehicle || g->remoteveh() != nullptr;
    draw_hints( w, cached_hints( driving ), point( 1, 0 ) );
    wnoutrefresh( w );
}

auto draw_menu_keyhints() -> void
{
    if( !g || g->uquit != QUIT_NO || !init::is_data_loaded() || !g->w_terrain ||
        !menu_context() || TERMX < 1 || TERMY < 1 ) {
        return;
    }
    const auto &panels = panel_manager::get_manager().get_current_layout();
    if( !std::ranges::any_of( panels, []( const auto & panel ) {
    return panel.get_name() == "Controls" && panel.toggle && panel.get_height() > 0;
    } ) ) {
        return;
    }
    static auto w = catacurses::window();
    if( !w || getmaxx( w ) != TERMX || getbegy( w ) != TERMY - 1 ) {
        w = catacurses::newwin( 1, TERMX, point( 0, TERMY - 1 ) );
    }
    werase( w );
    const auto label = std::string( _( "Controls:" ) );
    mvwprintz( w, point_zero, c_light_gray, label );
    draw_hints( w, cached_hints( false ), point( utf8_width( label ) + 1, 0 ) );
    wnoutrefresh( w );
}

auto show_welcome_once() -> void
{
    if( !get_option<bool>( "SHOW_WELCOME" ) ) {
    return;
}
const auto modern = get_option<std::string>( "CONTROL_SCHEME" ) == "modern";
const auto key = []( const action_id act ) { return colorize( action_route( act ), c_light_cyan ); };
    const auto key_id = []( const std::string & id ) { return colorize( action_route( id ), c_light_cyan ); };
    auto text = string_format(
                    _( "<color_white>Welcome to Bright Nights.</color>\n\n"
                       "Move with %1$s%2$s%3$s%4$s and step diagonally with %5$s%6$s%7$s%8$s.  %9$s waits a turn.\n" ),
                    key( ACTION_MOVE_FORTH ), key( ACTION_MOVE_LEFT ), key( ACTION_MOVE_BACK ),
                    key( ACTION_MOVE_RIGHT ), key( ACTION_MOVE_FORTH_LEFT ), key( ACTION_MOVE_FORTH_RIGHT ),
                    key( ACTION_MOVE_BACK_LEFT ), key( ACTION_MOVE_BACK_RIGHT ), key( ACTION_PAUSE ) );
    if( modern ) {
    text += string_format(
                _( "%1$s acts on the tile you face or select: doors, items, corpses, stairs.  Jump and Smash are always asked first.\n"
                   "%2$s opens inventory; pick an item for its actions, or press %3$s there to craft.  %4$s uses an item by its kind.\n"
                   "%5$s picks up underfoot; %6$s opens the pickup list.  %7$s lists every command; %8$s finds one by name.\n"
                   "%9$s selects a hostile and %10$s attacks it; walking into an enemy attacks too.  %11$s changes stance.\n"
                   "%12$s opens the map; %13$s opens missions, factions, zones and scores.\n" ),
                key( ACTION_EXAMINE ), key( ACTION_INVENTORY ),
                colorize( action_route( "CRAFT", "INVENTORY" ), c_light_cyan ), key( ACTION_USE_CONTEXTUAL ),
                key( ACTION_PICKUP ), key( ACTION_PICKUP_LIST ), key( ACTION_ACTIONMENU ),
                key( ACTION_SEARCH_ACTION ), key_id( "NEXT_TARGET" ), key( ACTION_FIRE ),
                key( ACTION_CYCLE_MOVE ), key( ACTION_MAP ), key( ACTION_WORLD_HUB ) );
        if( const auto peek = peek_keys( input_context( "DEFAULTMODE" ) ); !peek.empty() ) {
            text += string_format( _( "%s peeks around a corner, which takes time.\n" ),
                                   colorize( peek, c_light_cyan ) );
        }
        text += string_format(
                    _( "At a base, Quick stack and Sort pile in %s put things away without sorting zones.\n\n" ),
                    key( ACTION_ACTIONMENU ) );
    } else {
        text += string_format(
                    _( "%1$s interacts with things next to you, %2$s picks things up and %3$s opens your inventory.\n"
                       "%4$s uses an item, %5$s crafts, %6$s looks around and %7$s opens the map.\n\n"
                       "Back at a base, %8$s stashes what you carry onto nearby shelves that hold the same kind of thing, "
                       "and %9$s sorts the pile you are standing on.  No sorting zones needed.\n\n" ),
                    key( ACTION_EXAMINE ), key( ACTION_PICKUP_ALL ), key( ACTION_INVENTORY ),
                    key( ACTION_USE ), key( ACTION_CRAFT ), key( ACTION_LOOK ), key( ACTION_MAP ),
                    key( ACTION_QUICK_STACK ), key( ACTION_SORT_PILE ) );
    }
    if( !get_option<bool>( "MOUSE_MOVE" ) ) {
    text += modern ?
            _( "Left-click a nearby door, item or piece of furniture to use it, or an enemy to attack it; right-click selects a tile.  Clicks never walk.\n\n" )
                :
                _( "Right-click selects a map tile; left-click attacks an enemy.  Move with the keyboard, not mouse clicks.\n\n" );
    } else if( get_option<bool>( "MOUSE_TILE_SELECTION" ) ) {
    text += _( "Hover a tile to see what a click does, click to walk there or act, and right-click for every option.\n\n" );
    }
    if( !first_key( ACTION_AUTO_EXPLORE ).empty() ) {
    text += string_format( _( "%s walks toward ground you have not seen yet.\n\n" ),
                           key( ACTION_AUTO_EXPLORE ) );
    }
    text += string_format(
                _( "The Controls strip in the sidebar shows the main keys; %s on any screen lists every key." ),
                key( ACTION_KEYBINDINGS ) );
    popup( text );
    // Caves of Qud lets you pick Classic or Roleplay at the start; same here, using the existing death prompt.
    auto death = uilist();
    death.text = _( "How should death work?  You can change this later under Options, General." );
    death.addentry( 0, true, 'p', _( "Permadeath: a dead character stays dead" ) );
    death.addentry( 1, true, 'r', _( "Roleplay: offer to reload the last save when you die" ) );
    death.selected = get_option<bool>( "PROMPT_ON_CHARACTER_DEATH" ) ? 1 : 0;
    death.query();
    if( death.ret == 0 || death.ret == 1 ) {
    get_options().get_option( "PROMPT_ON_CHARACTER_DEATH" ).setValue( death.ret == 1 ? "true" :
            "false" );
    }
    get_options().get_option( "SHOW_WELCOME" ).setValue( "false" );
    get_options().save();
}

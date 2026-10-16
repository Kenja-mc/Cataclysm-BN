#include "keyhints_panel.h"

#include <string>
#include <vector>

#include "action.h"
#include "avatar.h"
#include "catacharset.h"
#include "color.h"
#include "cursesdef.h"
#include "game.h"
#include "input.h"
#include "options.h"
#include "output.h"
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
    const auto keys = keys_bound_to( act );
    return keys.empty() ? std::string() : key_name( keys.front() );
}

auto joined_keys( const std::vector<action_id> &acts ) -> std::string
{
    auto out = std::string();
    for( const auto act : acts ) {
        out += first_key( act );
    }
    return out;
}

auto collect_hints( const bool driving ) -> std::vector<hint>
{
    const auto singles = std::vector<std::pair<action_id, std::string>> {
        { ACTION_PAUSE, _( "wait" ) }, { ACTION_EXAMINE, _( "interact" ) }, { ACTION_PICKUP_ALL, _( "pick up" ) },
        { ACTION_INVENTORY, _( "inventory" ) }, { ACTION_USE, _( "use" ) }, { ACTION_WIELD, _( "wield" ) },
        { ACTION_AUTOATTACK, _( "attack" ) }, { ACTION_FIRE, _( "fire" ) }, { ACTION_RELOAD_ITEM, _( "reload" ) }, { ACTION_CRAFT, _( "craft" ) },
        { ACTION_QUICK_STACK, _( "stash" ) }, { ACTION_SORT_PILE, _( "sort pile" ) }, { ACTION_MAP, _( "map" ) },
        // Look goes last: it is the first to drop off a full strip, and hovering the map covers it.
        { ACTION_AUTO_EXPLORE, _( "explore" ) }, { ACTION_TOGGLE_PANEL_ADM, _( "sidebar" ) }, { ACTION_LOOK, _( "look" ) },
    };
    auto hints = std::vector<hint>();
    hints.reserve( singles.size() + 3 );
    auto push = [&]( std::string keys, std::string label ) {
        hint h;
        h.keys = std::move( keys );
        h.label = std::move( label );
        h.keys_width = utf8_width( h.keys );
        h.label_width = utf8_width( h.label );
        hints.push_back( std::move( h ) );
    };
    if( driving ) {
        push( joined_keys( { ACTION_MOVE_FORTH, ACTION_MOVE_BACK } ), _( "throttle" ) );
        push( joined_keys( { ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT } ), _( "steer" ) );
    } else {
        push( joined_keys( { ACTION_MOVE_FORTH, ACTION_MOVE_LEFT, ACTION_MOVE_BACK, ACTION_MOVE_RIGHT } ), _( "move" ) );
        push( joined_keys( { ACTION_MOVE_FORTH_LEFT, ACTION_MOVE_FORTH_RIGHT, ACTION_MOVE_BACK_LEFT, ACTION_MOVE_BACK_RIGHT } ), _( "diag" ) );
    }
    if( get_option<std::string>( "CONTROL_SCHEME" ) == "modern" ) {
        const auto ctxt = input_context( "DEFAULTMODE" );
        push( ctxt.get_desc( "action_menu" ), _( "menus" ) );
        push( "?", _( "all keys" ) );
        push( ctxt.get_desc( "NEXT_TARGET" ), _( "target" ) );
        push( first_key( ACTION_CYCLE_MOVE ), _( "stance" ) );
        push( joined_keys( { ACTION_SHIFT_N, ACTION_SHIFT_W, ACTION_SHIFT_S, ACTION_SHIFT_E } ),
              _( "look" ) );
        push( ctxt.get_desc( "PEEK_N" ), _( "peek north" ) );
    } else {
        push( "?", _( "all keys" ) );
    }
    for( const auto &[act, label] : singles ) {
        if( auto keys = first_key( act ); !keys.empty() ) {
            push( std::move( keys ), label );
        }
    }
    return hints;
}

} // namespace

auto draw_keyhints( const avatar &you, const catacurses::window &w ) -> void
{
    werase( w );
    const auto width = getmaxx( w ) - 1;
    const auto height = getmaxy( w );
    auto pos = point( 1, 0 );
    // Building the hints walks every binding; only redo it when bindings or driving mode change.
    static auto cached = std::vector<hint>();
    static auto cached_version = -1;
    static auto cached_driving = false;
    const auto driving = you.controlling_vehicle || g->remoteveh() != nullptr;
    if( cached_version != inp_mngr.bindings_version() || cached_driving != driving ) {
        cached = collect_hints( driving );
        cached_driving = driving;
        cached_version = inp_mngr.bindings_version();
    }
    for( const auto &h : cached ) {
        const auto len = h.keys_width + 1 + h.label_width;
        if( pos.x > 1 && pos.x + len > width ) {
            pos = point( 1, pos.y + 1 );
        }
        if( pos.y >= height ) {
            break;
        }
        mvwprintz( w, pos, c_light_cyan, h.keys );
        mvwprintz( w, pos + point( h.keys_width + 1, 0 ), c_dark_gray, h.label );
        pos.x += len + 2;
    }
    wnoutrefresh( w );
}

auto show_welcome_once() -> void
{
    if( !get_option<bool>( "SHOW_WELCOME" ) ) {
        return;
    }
    const auto key = []( const action_id act ) {
        const auto k = first_key( act );
        return colorize( k == _( "spc" ) ? std::string( _( "Space" ) ) : k, c_light_cyan );
    };
    auto text = string_format(
                    _( "<color_white>Welcome to Bright Nights.</color>\n\n"
                       "Move with %1$s%2$s%3$s%4$s and step diagonally with %5$s%6$s%7$s%8$s.  %9$s waits a turn.\n" ),
                    key( ACTION_MOVE_FORTH ), key( ACTION_MOVE_LEFT ), key( ACTION_MOVE_BACK ),
                    key( ACTION_MOVE_RIGHT ), key( ACTION_MOVE_FORTH_LEFT ), key( ACTION_MOVE_FORTH_RIGHT ),
                    key( ACTION_MOVE_BACK_LEFT ), key( ACTION_MOVE_BACK_RIGHT ), key( ACTION_PAUSE ) );
    if( get_option<std::string>( "CONTROL_SCHEME" ) == "modern" ) {
        const auto ctxt = input_context( "DEFAULTMODE" );
        const auto inventory_ctxt = input_context( "INVENTORY" );
        text += string_format(
                    _( "%1$s groups the secondary commands into menus; Info has your character and status screens.\n"
                       "%2$s opens inventory.  Select an item for Wield, Use, Eat or Drop; %3$s opens Craft from inventory.\n"
                       "%4$s interacts with the selected or nearby tile, including Open, Jump and Smash.  Destructive choices are explicit.\n"
                       "Shift + movement looks in that direction; Ctrl + movement peeks with the normal time cost.\n"
                       "%5$s cycles walking, running, crouching and prone.  %6$s selects a hostile target; %7$s attacks it.  You can also walk into adjacent enemies.\n"
                       "%8$s opens the map.  The Interact menu offers quick stack and sort pile for base storage, without sorting zones.\n\n" ),
                    key( ACTION_ACTIONMENU ), key( ACTION_INVENTORY ), inventory_ctxt.get_desc( "CRAFT" ),
                    key( ACTION_EXAMINE ), key( ACTION_CYCLE_MOVE ), ctxt.get_desc( "NEXT_TARGET" ),
                    key( ACTION_FIRE ), key( ACTION_MAP ) );
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
        text += _( "Right-click selects a map tile; left-click attacks an enemy.  Move with the keyboard, not mouse clicks.\n\n" );
    } else if( get_option<bool>( "MOUSE_TILE_SELECTION" ) ) {
        text += _( "Hover a tile to see what a click does, click to walk there or act, and right-click for every option.\n\n" );
    }
    if( !first_key( ACTION_AUTO_EXPLORE ).empty() ) {
        text += string_format( _( "%s walks toward ground you have not seen yet.\n\n" ),
                               key( ACTION_AUTO_EXPLORE ) );
    }
    text += _( "The Controls strip at the bottom of the sidebar shows the main keys; "
               "<color_light_cyan>?</color> on any screen lists every key." );
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

#include "keyhints_panel.h"

#include <string>
#include <vector>

#include "action.h"
#include "catacharset.h"
#include "color.h"
#include "cursesdef.h"
#include "output.h"
#include "translations.h"

namespace
{

struct hint {
    std::string keys;
    std::string label;
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

auto collect_hints() -> std::vector<hint>
{
    auto hints = std::vector<hint> {
        { .keys = joined_keys( { ACTION_MOVE_FORTH, ACTION_MOVE_LEFT, ACTION_MOVE_BACK, ACTION_MOVE_RIGHT } ), .label = _( "move" ) },
        { .keys = joined_keys( { ACTION_MOVE_FORTH_LEFT, ACTION_MOVE_FORTH_RIGHT, ACTION_MOVE_BACK_LEFT, ACTION_MOVE_BACK_RIGHT } ), .label = _( "diag" ) },
    };
    const auto singles = std::vector<std::pair<action_id, std::string>> {
        { ACTION_PAUSE, _( "wait" ) }, { ACTION_EXAMINE, _( "interact" ) }, { ACTION_PICKUP, _( "pick up" ) },
        { ACTION_INVENTORY, _( "inventory" ) }, { ACTION_USE, _( "use" ) }, { ACTION_WIELD, _( "wield" ) },
        { ACTION_FIRE, _( "fire" ) }, { ACTION_RELOAD_ITEM, _( "reload" ) }, { ACTION_CRAFT, _( "craft" ) },
        { ACTION_QUICK_STACK, _( "stash" ) }, { ACTION_SORT_PILE, _( "sort pile" ) }, { ACTION_LOOK, _( "look" ) },
        { ACTION_MAP, _( "map" ) },
    };
    for( const auto &[act, label] : singles ) {
        if( auto keys = first_key( act ); !keys.empty() ) {
            hints.push_back( { .keys = std::move( keys ), .label = label } );
        }
    }
    if( auto keys = first_key( ACTION_TOGGLE_PANEL_ADM ); !keys.empty() ) {
        hints.push_back( { .keys = std::move( keys ), .label = _( "sidebar" ) } );
    }
    hints.push_back( { .keys = "?", .label = _( "all keys" ) } );
    return hints;
}

} // namespace

auto draw_keyhints( const avatar &/*you*/, const catacurses::window &w ) -> void
{
    werase( w );
    const auto width = getmaxx( w ) - 1;
    const auto height = getmaxy( w );
    auto pos = point( 1, 0 );
    for( const auto &h : collect_hints() ) {
        const auto len = utf8_width( h.keys ) + 1 + utf8_width( h.label );
        if( pos.x > 1 && pos.x + len > width ) {
            pos = point( 1, pos.y + 1 );
        }
        if( pos.y >= height ) {
            break;
        }
        mvwprintz( w, pos, c_light_cyan, h.keys );
        mvwprintz( w, pos + point( utf8_width( h.keys ) + 1, 0 ), c_dark_gray, h.label );
        pos.x += len + 2;
    }
    wnoutrefresh( w );
}

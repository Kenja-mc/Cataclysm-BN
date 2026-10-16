#include "body_panel.h"

#include <algorithm>
#include <optional>
#include <string>
#include <vector>

#include "action.h"
#include "avatar.h"
#include "bodypart.h"
#include "catacharset.h"
#include "color.h"
#include "cursesdef.h"
#include "input.h"
#include "options.h"
#include "output.h"
#include "string_formatter.h"
#include "translations.h"

namespace
{

const efftype_id effect_bandaged( "bandaged" );
const efftype_id effect_bite( "bite" );
const efftype_id effect_bleed( "bleed" );
const efftype_id effect_disinfected( "disinfected" );
const efftype_id effect_infected( "infected" );
const efftype_id effect_mending( "mending" );

struct wound {
    std::string text;
    nc_color color;
};

/// Walks one limb's conditions worst first, visiting each wound.  Returning false
/// from `visit` stops the walk, so the compact "worst one only" case stays cheap.
template<typename Visit>
auto for_each_wound( const avatar &you, const bodypart_id &bp, Visit visit ) -> void
{
    if( you.get_part_hp_cur( bp ) <= 0 ) {
        const auto text = you.has_effect( effect_mending, bp.id() ) ? _( "mending" )
                                                                    : _( "broken" );
        if( !visit( wound{ text, c_magenta } ) ) {
            return;
        }
    }
    if( you.has_effect( effect_bleed, bp.id() ) ) {
        if( !visit( wound{ _( "bleeding" ), c_red } ) ) {
            return;
        }
    }
    if( you.has_effect( effect_infected, bp.id() ) ) {
        if( !visit( wound{ _( "infected" ), c_light_red } ) ) {
            return;
        }
    }
    if( you.has_effect( effect_bite, bp.id() ) ) {
        if( !visit( wound{ _( "bitten" ), c_yellow } ) ) {
            return;
        }
    }
    if( you.has_effect( effect_bandaged, bp.id() ) ) {
        if( !visit( wound{ _( "bandaged" ), c_light_green } ) ) {
            return;
        }
    }
    if( you.has_effect( effect_disinfected, bp.id() ) ) {
        if( !visit( wound{ _( "disinfected" ), c_light_cyan } ) ) {
            return;
        }
    }
}

/// Only the first (worst) wound for compact display.
auto first_wound_of( const avatar &you, const bodypart_id &bp ) -> std::optional<wound>
{
    auto out = std::optional<wound>();
    for_each_wound( you, bp, [&]( const wound & found ) {
        out = found;
        return false;
    } );
    return out;
}

/// What is wrong with one limb, worst first; treated conditions come last.
auto wounds_of( const avatar &you, const bodypart_id &bp ) -> std::vector<wound>
{
    auto out = std::vector<wound>();
    for_each_wound( you, bp, [&]( const wound & found ) {
        out.push_back( found );
        return true;
    } );
    return out;
}

} // namespace

namespace body_panel
{

auto draw( avatar &you, const catacurses::window &w ) -> void
{
    werase( w );
    // The worst problem of each hurt limb, then a hint for the full view.
    auto lines = std::vector<wound>();
    for( const auto &bp : you.get_all_body_parts( true ) ) {
        if( const auto found = first_wound_of( you, bp ) ) {
            lines.push_back( { string_format( "%s: %s", body_part_name_as_heading( bp, 1 ), found->text ),
                               found->color } );
        }
    }
    const auto rows = std::max( getmaxy( w ) - 1, 1 );
    if( lines.empty() ) {
        lines.push_back( { _( "No wounds" ), c_green } );
    } else if( static_cast<int>( lines.size() ) > rows ) {
        const auto more = lines.size() - rows + 1;
        lines.resize( rows - 1 );
        lines.push_back( { string_format( _( "And %d more" ), more ), c_light_gray } );
    }
    const auto width = std::max( getmaxx( w ), 1 );
    for( int i = 0; i < static_cast<int>( lines.size() ) && i < rows; i++ ) {
        trim_and_print( w, point( 0, i ), width, lines[i].color, lines[i].text );
    }
    // Looking the key up walks every binding, so only redo it when bindings change.
    static auto key = std::string();
    static auto key_version = -1;
    if( key_version != inp_mngr.bindings_version() ) {
        key = press_x( ACTION_BODY_STATUS, "", "", "" );
        if( key.empty() && get_option<std::string>( "CONTROL_SCHEME" ) == "modern" ) {
            key = string_format( _( "%s → Info" ), press_x( ACTION_ACTIONMENU, "", "", "" ) );
        }
        key_version = inp_mngr.bindings_version();
    }
    if( !key.empty() ) {
        // Right under the wounds, so a short list leaves no gap where the figure was.
        const auto row = std::min( rows, static_cast<int>( lines.size() ) );
        trim_and_print( w, point( 0, row ), width, c_dark_gray,
                        string_format( _( "%s: details" ), key ) );
    }
    wnoutrefresh( w );
}

auto show_details( avatar &you ) -> void
{
    auto text = std::string();
    for( const auto &bp : you.get_all_body_parts( true ) ) {
        const auto [bar, bar_color] = get_hp_bar( you.get_part_hp_cur( bp ), you.get_part_hp_max( bp ) );
        auto name = body_part_name_as_heading( bp, 1 );
        name += std::string( std::max( 0, 10 - utf8_width( name ) ), ' ' );
        text += colorize( name, c_white ) + " " + colorize( bar, bar_color ) +
                string_format( " %d/%d", you.get_part_hp_cur( bp ), you.get_part_hp_max( bp ) );
        for( const auto &w : wounds_of( you, bp ) ) {
            text += "  " + colorize( w.text, w.color );
        }
        text += "\n";
    }
    if( you.get_perceived_pain() > 0 ) {
        text += "\n" + string_format( _( "Pain: %d" ), you.get_perceived_pain() ) + "\n";
    }
    text += "\n" + colorize( _( "Bandages stop bleeding, disinfectant prevents infection, splints help broken limbs mend." ),
                             c_dark_gray );
    popup( text );
}

} // namespace body_panel

#include "body_panel.h"

#include <algorithm>
#include <string>
#include <vector>

#include "action.h"
#include "avatar.h"
#include "bodypart.h"
#include "catacharset.h"
#include "color.h"
#include "cursesdef.h"
#include "input.h"
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

/// What is wrong with one limb, worst first; treated conditions come last.
auto wounds_of( const avatar &you, const bodypart_id &bp ) -> std::vector<wound>
{
    auto out = std::vector<wound>();
    if( you.get_part_hp_cur( bp ) <= 0 ) {
        out.push_back( { you.has_effect( effect_mending, bp.id() ) ? _( "mending" ) : _( "broken" ), c_magenta } );
    }
    if( you.has_effect( effect_bleed, bp.id() ) ) {
        out.push_back( { _( "bleeding" ), c_red } );
    }
    if( you.has_effect( effect_infected, bp.id() ) ) {
        out.push_back( { _( "infected" ), c_light_red } );
    }
    if( you.has_effect( effect_bite, bp.id() ) ) {
        out.push_back( { _( "bitten" ), c_yellow } );
    }
    if( you.has_effect( effect_bandaged, bp.id() ) ) {
        out.push_back( { _( "bandaged" ), c_light_green } );
    }
    if( you.has_effect( effect_disinfected, bp.id() ) ) {
        out.push_back( { _( "disinfected" ), c_light_cyan } );
    }
    return out;
}

auto health_color( const avatar &you, const bodypart_id &bp ) -> nc_color
{
    const auto cur = you.get_part_hp_cur( bp );
    const auto max = std::max( you.get_part_hp_max( bp ), 1 );
    return cur <= 0 ? c_dark_gray : cur * 4 > max * 3 ? c_green : cur * 2 > max ? c_yellow :
           cur * 4 > max ? c_light_red : c_red;
}

struct figure_part {
    const char *bp;
    point pos;
    const char *glyph;
};

/// A front view, so the character's right arm is on the left of the screen.
const std::vector<figure_part> figure = {
    { "head", { 2, 0 }, "O" },
    { "arm_r", { 1, 1 }, "/" }, { "torso", { 2, 1 }, "|" }, { "arm_l", { 3, 1 }, "\\" },
    { "torso", { 2, 2 }, "|" },
    { "leg_r", { 1, 3 }, "/" }, { "leg_l", { 3, 3 }, "\\" },
};

} // namespace

namespace body_panel
{

auto draw( avatar &you, const catacurses::window &w ) -> void
{
    werase( w );
    for( const auto &part : figure ) {
        const auto bp = bodypart_id( part.bp );
        mvwprintz( w, part.pos + point( 1, 0 ), health_color( you, bp ), part.glyph );
    }
    // Beside the figure: the worst problem of each hurt limb, then a hint for the full view.
    auto lines = std::vector<std::pair<std::string, nc_color>>();
    for( const auto &bp : you.get_all_body_parts( true ) ) {
        const auto found = wounds_of( you, bp );
        if( !found.empty() ) {
            lines.emplace_back( string_format( "%s: %s", body_part_name_as_heading( bp, 1 ), found.front().text ),
                                found.front().color );
        }
    }
    const auto rows = std::max( getmaxy( w ) - 1, 1 );
    if( lines.empty() ) {
        lines.emplace_back( _( "No wounds" ), c_green );
    } else if( static_cast<int>( lines.size() ) > rows ) {
        const auto more = lines.size() - rows + 1;
        lines.resize( rows - 1 );
        lines.emplace_back( string_format( _( "and %d more" ), more ), c_light_gray );
    }
    const auto text_x = 7;
    for( int i = 0; i < static_cast<int>( lines.size() ) && i < rows; i++ ) {
        trim_and_print( w, point( text_x, i ), getmaxx( w ) - text_x - 1, lines[i].second, lines[i].first );
    }
    // Looking the key up walks every binding, so only redo it when bindings change.
    static auto key = std::string();
    static auto key_version = -1;
    if( key_version != inp_mngr.bindings_version() ) {
        key = press_x( ACTION_BODY_STATUS, "", "", "" );
        key_version = inp_mngr.bindings_version();
    }
    if( !key.empty() ) {
        trim_and_print( w, point( text_x, rows ), getmaxx( w ) - text_x - 1, c_dark_gray,
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

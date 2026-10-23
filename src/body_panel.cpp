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
#include "popup.h"
#include "scrollbar_input.h"
#include "string_formatter.h"
#include "translations.h"
#include "ui_manager.h"

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

/// The full per-limb report shown by the h key.
auto report_text( avatar &you ) -> std::string
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
    return text;
}

/// The Modern body report: the wheel scrolls a long report, the scrollbar shows
/// the position and is clickable, and Close (or Escape) leaves.  Information
/// only: no click here spends moves or touches the body.
auto show_details_mouse( const std::string &text ) -> void
{
    constexpr auto border = 1;
    constexpr auto scrollbar_width = 1;
    constexpr auto button_height = 1;
    constexpr auto wheel_step = 3;

    const auto max_text_width = std::max( 1, FULL_SCREEN_WIDTH - 2 * border - scrollbar_width );
    const auto lines = foldstring( text, max_text_width );
    auto content_width = 0;
    for( const auto &line : lines ) {
        content_width = std::max( content_width, utf8_width( line, true ) );
    }
    auto ctxt = input_context( "BODY_REPORT" );
    ctxt.register_action( "QUIT" );
    ctxt.register_action( "HELP_KEYBINDINGS" );
    ctxt.register_action( "COORDINATE" );
    ctxt.register_action( "MOUSE_MOVE" );
    ctxt.register_action( "SELECT" );
    ctxt.register_action( "SCROLL_UP" );
    ctxt.register_action( "SCROLL_DOWN" );
    const auto close_label = ctxt.get_desc( "QUIT", _( "Close" ) );
    const auto close_label_width = utf8_width( close_label, true );
    content_width = std::max( content_width, close_label_width );

    // Everything below is recomputed on resize, because the window and the
    // cells the mouse is tested against must match what is drawn.
    auto viewport = 0;
    auto win_width = 0;
    auto win_height = 0;
    auto scrollable = false;
    auto scrollbar_pos = point_zero;
    auto close_pos = point_zero;
    auto scroll_pos = 0;
    auto hover_close = false;

    catacurses::window win;
    ui_adaptor ui;
    ui.on_screen_resize( [&]( ui_adaptor & ) {
        const auto max_viewport = std::max( 1, TERMY - 2 * border - button_height );
        scrollable = static_cast<int>( lines.size() ) > max_viewport;
        viewport = std::min<int>( lines.size(), max_viewport );
        win_width = std::min( TERMX, content_width + 2 * border + scrollbar_width );
        win_height = viewport + 2 * border + button_height;
        // The scrollbar takes the column left of the right border.
        scrollbar_pos = point( win_width - 1 - scrollbar_width, border );
        close_pos = point( std::max( border, ( win_width - close_label_width ) / 2 ),
                           win_height - 1 - border );
        scroll_pos = std::clamp( scroll_pos, 0,
                                 std::max( 0, static_cast<int>( lines.size() ) - viewport ) );
        const auto origin = point( std::max( 0, ( TERMX - win_width ) / 2 ),
                                   std::max( 0, ( TERMY - win_height ) / 2 ) );
        win = catacurses::newwin( win_height, win_width, origin );
        ui.position_from_window( win );
    } );
    ui.mark_resize();
    ui.on_redraw( [&]( ui_adaptor & ) {
        ui.disable_cursor();
        werase( win );
        draw_border( win );
        for( auto row = 0; row < viewport; ++row ) {
            const auto line = static_cast<size_t>( scroll_pos + row );
            if( line >= lines.size() ) {
                break;
            }
            auto col = c_white;
            print_colored_text( win, point( border, border + row ), col, col, lines[line] );
        }
        if( scrollable ) {
            scrollbar()
            .offset_x( scrollbar_pos.x )
            .offset_y( scrollbar_pos.y )
            .content_size( static_cast<int>( lines.size() ) )
            .viewport_pos( scroll_pos )
            .viewport_size( viewport )
            .scroll_to_last( true )
            .apply( win );
        }
        mvwprintz( win, close_pos, hover_close ? hilite( c_white ) : c_white, close_label );
        wnoutrefresh( win );
    } );

    auto done = false;
    while( !done ) {
        ui_manager::redraw_invalidated();
        const std::string &action = ctxt.handle_input();
        if( action == "QUIT" ) {
            done = true;
        } else if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
            if( scrollable ) {
                // Text view convention: the wheel turns three lines per notch.
                scroll_pos = std::clamp(
                                 scroll_pos + ( action == "SCROLL_DOWN" ? wheel_step : -wheel_step ), 0,
                                 static_cast<int>( lines.size() ) - viewport );
                ui.invalidate_ui();
            }
        } else if( action == "MOUSE_MOVE" || action == "SELECT" ) {
            const auto mouse = ctxt.get_coordinates( win );
            auto now_hover = false;
            if( mouse ) {
                // get_coordinates() is relative to the window centre.
                const auto cell = mouse->xy().raw() + point( getmaxx( win ), getmaxy( win ) ) / 2;
                if( cell.y == close_pos.y && cell.x >= close_pos.x &&
                    cell.x < close_pos.x + close_label_width ) {
                    now_hover = true;
                    if( action == "SELECT" ) {
                        done = true;
                    }
                } else if( scrollable && action == "SELECT" && cell.x == scrollbar_pos.x &&
                           cell.y >= scrollbar_pos.y && cell.y < scrollbar_pos.y + viewport ) {
                    const auto hit = scrollbar_input::click(
                    scrollbar_input::geometry{
                        .offset = scrollbar_pos,
                        .viewport_size = viewport,
                        .content_size = static_cast<int>( lines.size() ),
                        .viewport_pos = scroll_pos,
                        .scroll_to_last = true,
                    }, cell );
                    if( hit ) {
                        // A text view shows whole pages, so the bar's last row
                        // is the first row of the last page.
                        scroll_pos = std::min( hit->viewport_pos,
                                               static_cast<int>( lines.size() ) - viewport );
                        ui.invalidate_ui();
                    }
                }
            }
            if( now_hover != hover_close ) {
                hover_close = now_hover;
                ui.invalidate_ui();
            }
        }
    }
}

auto show_details( avatar &you ) -> void
{
    if( get_option<std::string>( "CONTROL_SCHEME" ) == "modern" ) {
        show_details_mouse( report_text( you ) );
        return;
    }
    // Classic keeps the plain upstream popup.
    popup( report_text( you ) );
}

} // namespace body_panel

#include "distraction_manager.h"

#include <functional>
#include <fstream>
#include <optional>
#include <string>

#include "cata_utility.h"
#include "color.h"
#include "cursesdef.h"
#include "input.h"
#include "json.h"
#include "options.h"
#include "output.h"
#include "path_info.h"
#include "point.h"
#include "scrollbar_input.h"
#include "translations.h"
#include "ui.h"
#include "ui_manager.h"
#include "uistate.h"
#include "fstream_utils.h"

namespace io
{
template<>
std::string enum_to_string<distraction_type>( distraction_type data )
{
    switch( data ) {
            // *INDENT-OFF*
        case distraction_type::alert: return "Alert";
        case distraction_type::noise: return "Noise";
        case distraction_type::pain: return "Pain";
        case distraction_type::attacked: return "Attacked";
        case distraction_type::hostile_spotted_far: return "Hostile Far";
        case distraction_type::hostile_spotted_near: return "Hostile Near";
        case distraction_type::talked_to: return "Talk";
        case distraction_type::asthma: return "Asthma";
        case distraction_type::weather_change: return "Weather Change";
            // *INDENT-ON*
        case distraction_type::num_distraction_type:
            break;
    }
    debugmsg( "Invalid distraction_type" );
    abort();
}
} // namespace io

namespace distraction_manager
{

static const std::map< distraction_type, std::pair< std::string, std::string> >
distraction_desc = {
    {distraction_type::noise,                { translate_marker( "Noise" ),                     translate_marker( "Interrupts you if you hear a noise." ) } },
    {distraction_type::pain,                 { translate_marker( "Pain" ),                      translate_marker( "Interrupts you if you feel pain." ) } },
    {distraction_type::attacked,             { translate_marker( "Attacked" ),                  translate_marker( "Interrupts you if you are hurt." ) } },
    {distraction_type::hostile_spotted_far,  { translate_marker( "Hostile Spotted" ),           translate_marker( "Interrupts you if you see an enemy." ) } },
    {distraction_type::hostile_spotted_near, { translate_marker( "Hostile Dangerously Close" ), translate_marker( "Interrupts you if an enemy comes within 5 squares." ) } },
    {distraction_type::talked_to,            { translate_marker( "Conversation" ),              translate_marker( "Interrupts you if someone starts a conversation." ) } },
    {distraction_type::asthma,               { translate_marker( "Asthma" ),                    translate_marker( "Interrupts you if you have an asthma attack." ) } },
    {distraction_type::weather_change,       { translate_marker( "Weather change" ),            translate_marker( "Interrupts you if the weather becomes dangerous." ) } }
};

void distraction_manager_gui::show()
{
    const int iHeaderHeight = 4;
    int iContentHeight = 0;
    const int num_distractions = distraction_desc.size();
    catacurses::window w_border;
    catacurses::window w_header;
    catacurses::window w;

    ui_adaptor ui;
    ui.on_screen_resize( [&]( ui_adaptor & ui ) {
        iContentHeight = FULL_SCREEN_HEIGHT - 2 - iHeaderHeight;

        const point iOffset( TERMX > FULL_SCREEN_WIDTH ? ( TERMX - FULL_SCREEN_WIDTH ) / 2 : 0,
                             TERMY > FULL_SCREEN_HEIGHT ? ( TERMY - FULL_SCREEN_HEIGHT ) / 2 : 0 );

        w_border = catacurses::newwin( FULL_SCREEN_HEIGHT, FULL_SCREEN_WIDTH,
                                       iOffset );

        w_header = catacurses::newwin( iHeaderHeight, FULL_SCREEN_WIDTH - 2,
                                       iOffset + point_south_east );

        w = catacurses::newwin( iContentHeight, FULL_SCREEN_WIDTH - 2,
                                iOffset + point( 1, iHeaderHeight + 1 ) );

        ui.position_from_window( w_border );
    } );
    ui.mark_resize();

    std::vector<distraction_type> distractions_status;
    distractions_status.reserve( distraction_desc.size() );
    for( auto &dist : distraction_desc ) {
        distractions_status.emplace_back( dist.first );
    };

    int currentLine = 0;
    int startPosition = 0;
    distraction_type cur_distraction = distractions_status[currentLine];

    input_context ctx{ "DISTRACTION_MANAGER" };
    ctx.register_cardinal();
    ctx.register_action( "QUIT" );
    ctx.register_action( "HELP_KEYBINDINGS" );
    ctx.register_action( "CONFIRM" );
    const auto modern = get_option<std::string>( "CONTROL_SCHEME" ) == "modern";
    if( modern ) {
        ctx.register_action( "COORDINATE" );
        ctx.register_action( "MOUSE_MOVE" );
        ctx.register_action( "SELECT" );
        ctx.register_action( "SEC_SELECT" );
        ctx.register_action( "SCROLL_UP" );
        ctx.register_action( "SCROLL_DOWN" );
    }

    // Matches the draw_scrollbar() call in on_redraw below.
    const auto scrollbar_geometry = [&]() {
        return scrollbar_input::geometry{
            .offset = point( 0, iHeaderHeight + 1 ),
            .viewport_size = iContentHeight,
            .content_size = num_distractions,
            .viewport_pos = currentLine,
            .scroll_to_last = true,
        };
    };
    // Row of the last plain click, -1 when the next click starts a new pair.
    auto last_click_row = -1;
    // A row click leaves the view where it is, so a second click hits the same row.
    auto preserve_view = false;

    ui.on_redraw( [&]( const ui_adaptor & ) {
        // Draw border
        draw_border( w_border, BORDER_COLOR, _( "Distractions manager" ) );
        mvwputch( w_border, point( 0, iHeaderHeight - 1 ), c_light_gray, LINE_XXXO );
        mvwputch( w_border, point( 79, iHeaderHeight - 1 ), c_light_gray, LINE_XOXX );
        mvwputch( w_border, point( 61, FULL_SCREEN_HEIGHT - 1 ), c_light_gray, LINE_XXOX );
        wnoutrefresh( w_border );

        // Draw header
        werase( w_header );
        fold_and_print( w_header, point_zero, getmaxx( w_header ), c_white,
                        _( distraction_desc.at( cur_distraction ).second.c_str() ) );

        // Draw horizontal line and corner pieces of the table
        for( int x = 0; x < 78; x++ ) {
            if( x == 60 ) {
                mvwputch( w_header, point( x, iHeaderHeight - 2 ), c_light_gray, LINE_OXXX );
                mvwputch( w_header, point( x, iHeaderHeight - 1 ), c_light_gray, LINE_XOXO );
            } else {
                mvwputch( w_header, point( x, iHeaderHeight - 2 ), c_light_gray, LINE_OXOX );
            }
        }

        wnoutrefresh( w_header );

        // Clear table
        for( int y = 0; y < iContentHeight; y++ ) {
            for( int x = 0; x < 79; x++ ) {
                if( x == 60 ) {
                    mvwputch( w, point( x, y ), c_light_gray, LINE_XOXO );
                } else {
                    mvwputch( w, point( x, y ), c_black, ' ' );
                }
            }
        }

        const auto sb = scrollbar_geometry();
        draw_scrollbar( w_border, sb.viewport_pos, sb.viewport_size, sb.content_size, sb.offset );

        if( preserve_view ) {
            if( startPosition > currentLine ) {
                startPosition = currentLine;
            }
            if( currentLine >= startPosition + iContentHeight ) {
                startPosition = currentLine - iContentHeight + 1;
            }
        } else {
            calcStartPos( startPosition, currentLine, iContentHeight, num_distractions );
        }

        for( int i = startPosition; i < num_distractions; ++i ) {
            if( !distractions.contains( distractions_status[i] ) ) {
                debugmsg( "Distraction not valid for Distraction Manager" );
                continue;
            }

            const nc_color line_color = i == currentLine ? hilite( c_white ) : c_white;
            const nc_color status_color = distractions.at(
                                              distractions_status[i] ) ? c_red : c_light_green;
            const std::string status_string = distractions.at( distractions_status[i] ) ? _( "Disabled" ) :
                                              _( "Enabled" );

            // Print distraction types
            mvwprintz( w, point( 1, i - startPosition ), line_color, "%s",
                       _( distraction_desc.at( distractions_status[i] ).first.c_str() ) );

            // Print "Enabled/Disabled" text
            mvwprintz( w, point( 62, i - startPosition ), status_color, "%s", status_string );
        }

        wnoutrefresh( w_header );
        wnoutrefresh( w_border );
        wnoutrefresh( w );
    } );

    while( true ) {
        ui_manager::redraw();

        auto currentAction = ctx.handle_input();

        // get_coordinates() is relative to the window centre.
        const auto cell_in = [&]( const catacurses::window & win ) -> std::optional<point> {
            const auto mouse = ctx.get_coordinates( win );
            if( !mouse ) {
                return std::nullopt;
            }
            const auto cell = mouse->xy().raw() + point( getmaxx( win ), getmaxy( win ) ) / 2;
            if( cell.x < 0 || cell.y < 0 || cell.x >= getmaxx( win ) || cell.y >= getmaxy( win ) ) {
                return std::nullopt;
            }
            return cell;
        };

        auto mouse_hover = false;
        auto mouse_handled = false;
        if( modern && currentAction == "MOUSE_MOVE" ) {
            // Hover never changes the selection.
            currentAction.clear();
            mouse_hover = true;
        } else if( modern && currentAction == "SEC_SELECT" ) {
            // Right click cancels, like the other modern list menus.
            currentAction = "QUIT";
            mouse_handled = true;
        } else if( modern && currentAction == "SELECT" ) {
            mouse_handled = true;
            auto consumed = false;
            if( const auto border_cell = cell_in( w_border ) ) {
                if( const auto hit = scrollbar_input::click( scrollbar_geometry(), *border_cell ) ) {
                    currentLine = hit->viewport_pos;
                    cur_distraction = distractions_status[currentLine];
                    last_click_row = -1;
                    preserve_view = false;
                    consumed = true;
                }
            }
            if( !consumed ) {
                if( const auto cell = cell_in( w ) ) {
                    const auto row = startPosition + cell->y;
                    if( cell->y < iContentHeight && row < num_distractions ) {
                        if( row == last_click_row ) {
                            // The second click on the same row runs Enter.
                            currentAction = "CONFIRM";
                            last_click_row = -1;
                            preserve_view = false;
                        } else {
                            currentLine = row;
                            cur_distraction = distractions_status[currentLine];
                            last_click_row = row;
                            preserve_view = true;
                        }
                    }
                    consumed = true;
                }
            }
            if( !consumed ) {
                // A click outside the drawn controls does nothing.
                currentAction.clear();
                last_click_row = -1;
                preserve_view = false;
            }
        }
        if( !mouse_handled && !mouse_hover ) {
            // Keyboard and wheel input end a click pair.
            last_click_row = -1;
            preserve_view = false;
        }

        if( currentAction == "QUIT" ) {
            save();
            break;
        }

        if( currentAction == "UP" || currentAction == "SCROLL_UP" ) {
            currentLine = modulo( currentLine - 1, num_distractions );
            cur_distraction = distractions_status[currentLine];
        } else if( currentAction == "DOWN" || currentAction == "SCROLL_DOWN" ) {
            currentLine = modulo( currentLine + 1, num_distractions );
            cur_distraction = distractions_status[currentLine];
        } else if( currentAction == "CONFIRM" ) {
            // This will change status color and status text
            distractions[cur_distraction] = !distractions[cur_distraction];
        }
    }
}

bool distraction_manager_gui::is_ignored( distraction_type &distract )
{
    // If it doesn't exist it'll create one with a null/false value which works fine for us.
    return distractions[distract];
}

bool distraction_manager_gui::save()
{
    auto file = PATH_INFO::distraction();

    return write_to_file( file, [&]( std::ostream & fout ) {
        JsonOut jout( fout, true );
        distraction_manager_gui::serialize( jout );

    }, _( "distraction manager configuration" ) );
}

void distraction_manager_gui::load()
{
    distractions.clear();
    for( int i = 0; i < static_cast<int>( distraction_type::num_distraction_type ); ++i ) {
        distractions.emplace( static_cast<distraction_type>( i ), false );
    }

    std::ifstream distr;
    std::string file = PATH_INFO::distraction();

    distr.open( file.c_str(), std::ifstream::in | std::ifstream::binary );

    if( distr.good() ) {
        try {
            JsonIn jsin( distr );
            deserialize( jsin );
        } catch( const JsonError &e ) {
            debugmsg( "Error while loading distraction manager settings: %s", e.what() );
        }
    }

    distr.close();
}

void distraction_manager_gui::serialize( JsonOut &json ) const
{
    json.start_array();

    for( auto &elem : distractions ) {
        json.start_object();

        json.member( "Distraction Type", io::enum_to_string<distraction_type>( elem.first ) );
        json.member( "Bool", elem.second );

        json.end_object();
    }

    json.end_array();
}

void distraction_manager_gui::deserialize( JsonIn &jsin )
{
    jsin.start_array();
    while( !jsin.end_array() ) {
        JsonObject jo = jsin.get_object();

        if( !jo.has_string( "Distraction Type" ) ) {
            continue;
        }

        const distraction_type type_id = jo.get_enum_value<distraction_type>( "Distraction Type" );
        const bool boolean = jo.get_bool( "Bool" );

        distractions[type_id] = boolean;
    }
}

} // namespace distraction_manager

distraction_manager::distraction_manager_gui &get_distraction_manager()
{
    static distraction_manager::distraction_manager_gui staticSettings;
    return staticSettings;
}

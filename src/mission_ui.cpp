#include "game.h" // IWYU pragma: associated

#include <algorithm>
#include <map>
#include <optional>
#include <string>
#include <vector>

#include "avatar.h"
#include "calendar.h"
#include "color.h"
#include "debug.h"
#include "input.h"
#include "mission.h"
#include "npc.h"
#include "options.h"
#include "output.h"
#include "scrollbar_input.h"
#include "string_formatter.h"
#include "string_utils.h"
#include "tab_input.h"
#include "translations.h"
#include "ui.h"
#include "ui_manager.h"

void game::list_missions()
{
    catacurses::window w_missions;

    enum class tab_mode : int {
        TAB_ACTIVE = 0,
        TAB_COMPLETED,
        TAB_FAILED,
        NUM_TABS,
        FIRST_TAB = 0,
        LAST_TAB = NUM_TABS - 1
    };
    tab_mode tab = tab_mode::FIRST_TAB;
    size_t selection = 0;
    int entries_per_page = 0;
    input_context ctxt( "MISSIONS" );
    ctxt.register_cardinal();
    ctxt.register_action( "CONFIRM" );
    ctxt.register_action( "QUIT" );
    ctxt.register_action( "HELP_KEYBINDINGS" );
    const bool modern = get_option<std::string>( "CONTROL_SCHEME" ) == "modern";
    if( modern ) {
        ctxt.register_action( "COORDINATE" );
        ctxt.register_action( "MOUSE_MOVE" );
        ctxt.register_action( "SELECT" );
        ctxt.register_action( "SEC_SELECT" );
        ctxt.register_action( "SCROLL_UP" );
        ctxt.register_action( "SCROLL_DOWN" );
    }

    ui_adaptor ui;
    ui.on_screen_resize( [&]( ui_adaptor & ui ) {
        w_missions = new_centered_win( FULL_SCREEN_HEIGHT, FULL_SCREEN_WIDTH );

        // content ranges from y=3 to FULL_SCREEN_HEIGHT - 2
        entries_per_page = FULL_SCREEN_HEIGHT - 4;

        ui.position_from_window( w_missions );
    } );
    ui.mark_resize();

    std::vector<mission *> umissions;

    ui.on_redraw( [&]( const ui_adaptor & ) {
        werase( w_missions );
        // entries_per_page * page number
        const int top_of_page = entries_per_page * ( selection / entries_per_page );
        const int bottom_of_page =
            std::min( top_of_page + entries_per_page - 1, static_cast<int>( umissions.size() ) - 1 );

        for( int i = 3; i < FULL_SCREEN_HEIGHT - 1; i++ ) {
            mvwputch( w_missions, point( 30, i ), BORDER_COLOR, LINE_XOXO );
        }

        const std::vector<std::pair<tab_mode, std::string>> tabs = {
            { tab_mode::TAB_ACTIVE, _( "ACTIVE MISSIONS" ) },
            { tab_mode::TAB_COMPLETED, _( "COMPLETED MISSIONS" ) },
            { tab_mode::TAB_FAILED, _( "FAILED MISSIONS" ) },
        };
        draw_tabs( w_missions, tabs, tab );
        draw_border_below_tabs( w_missions );

        mvwputch( w_missions, point( 30, 2 ), BORDER_COLOR,
                  tab == tab_mode::TAB_COMPLETED ? ' ' : LINE_OXXX ); // ^|^
        mvwputch( w_missions, point( 30, FULL_SCREEN_HEIGHT - 1 ), BORDER_COLOR, LINE_XXOX ); // _|_

        draw_scrollbar( w_missions, selection, entries_per_page, umissions.size(), point( 0, 3 ) );

        for( int i = top_of_page; i <= bottom_of_page; i++ ) {
            const auto miss = umissions[i];
            const nc_color col = u.get_active_mission() == miss ? c_light_green : c_white;
            const int y = i - top_of_page + 3;
            trim_and_print( w_missions, point( 1, y ), 28,
                            static_cast<int>( selection ) == i ? hilite( col ) : col,
                            miss->name() );
        }

        if( selection < umissions.size() ) {
            const auto miss = umissions[selection];
            const nc_color col = u.get_active_mission() == miss ? c_light_green : c_white;
            std::string for_npc;
            if( miss->get_npc_id().is_valid() ) {
                npc *guy = g->find_npc( miss->get_npc_id() );
                if( guy ) {
                    for_npc = string_format( _( " for %s" ), guy->disp_name() );
                }
            }

            int y = 3;
            y += fold_and_print( w_missions, point( 31, y ), getmaxx( w_missions ) - 33, col,
                                 miss->name() + for_npc );

            auto format_tokenized_description = []( const std::string & description,
            const std::vector<std::pair<int, itype_id>> &rewards ) {
                std::string formatted_description = description;
                for( const auto &reward : rewards ) {
                    std::string token = "<reward_count:" + reward.second.str() + ">";
                    formatted_description = replace_all( formatted_description, token,
                                                         string_format( "%d", reward.first ) );
                }
                return formatted_description;
            };

            y++;
            if( !miss->get_description().empty() ) {
                y += fold_and_print( w_missions, point( 31, y ), getmaxx( w_missions ) - 33, c_white,
                                     format_tokenized_description( miss->get_description(), miss->get_likely_rewards() ) );
            }
            if( miss->has_deadline() ) {
                const time_point deadline = miss->get_deadline();
                mvwprintz( w_missions, point( 31, ++y ), c_white, _( "Deadline: %s" ), to_string( deadline ) );

                if( tab != tab_mode::TAB_COMPLETED ) {
                    // There's no point in displaying this for a completed mission.
                    // @ TODO: But displaying when you completed it would be useful.
                    const time_duration remaining = deadline - calendar::turn;
                    std::string remaining_time;

                    if( remaining <= 0_turns ) {
                        remaining_time = _( "None!" );
                    } else if( u.has_watch() ) {
                        remaining_time = to_string( remaining );
                    } else {
                        remaining_time = to_string_approx( remaining );
                    }

                    mvwprintz( w_missions, point( 31, ++y ), c_white, _( "Time remaining: %s" ), remaining_time );
                }
            }
            if( miss->has_target() ) {
                const tripoint_abs_omt pos = u.abs_omt_pos();
                // TODO: target does not contain a z-component, targets are assumed to be on z=0
                mvwprintz( w_missions, point( 31, ++y ), c_white, _( "Target: %s   You: %s" ),
                           miss->get_target().to_string(), pos.to_string() );
            }
        } else {
            static const std::map< tab_mode, std::string > nope = {
                { tab_mode::TAB_ACTIVE, translate_marker( "You have no active missions!" ) },
                { tab_mode::TAB_COMPLETED, translate_marker( "You haven't completed any missions!" ) },
                { tab_mode::TAB_FAILED, translate_marker( "You haven't failed any missions!" ) }
            };
            mvwprintz( w_missions, point( 31, 4 ), c_light_red, _( nope.at( tab ) ) );
        }

        wnoutrefresh( w_missions );
    } );

    std::optional<size_t> mouse_row;

    while( true ) {
        umissions.clear();
        if( tab < tab_mode::FIRST_TAB || tab >= tab_mode::NUM_TABS ) {
            debugmsg( "The sanity check failed because tab=%d", static_cast<int>( tab ) );
            tab = tab_mode::FIRST_TAB;
        }
        switch( tab ) {
            case tab_mode::TAB_ACTIVE:
                umissions = u.get_active_missions();
                break;
            case tab_mode::TAB_COMPLETED:
                umissions = u.get_completed_missions();
                break;
            case tab_mode::TAB_FAILED:
                umissions = u.get_failed_missions();
                break;
            default:
                break;
        }
        if( ( !umissions.empty() && selection >= umissions.size() ) ||
            ( umissions.empty() && selection != 0 ) ) {
            debugmsg( "Sanity check failed: selection=%d, size=%d", static_cast<int>( selection ),
                      static_cast<int>( umissions.size() ) );
            selection = 0;
        }
        ui_manager::redraw();
        std::string action = ctxt.handle_input();
        if( modern && ctxt.get_raw_input().type == input_event_t::mouse ) {
            if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
                action = action == "SCROLL_UP" ? "UP" : "DOWN";
                mouse_row.reset();
            } else if( action == "SELECT" || action == "SEC_SELECT" ) {
                action.clear();
                if( const auto mouse = ctxt.get_coordinates( w_missions ) ) {
                    const auto cell = mouse->xy().raw() + point( getmaxx( w_missions ),
                                      getmaxy( w_missions ) ) / 2;
                    const std::vector<std::string> tab_texts = {
                        _( "ACTIVE MISSIONS" ), _( "COMPLETED MISSIONS" ), _( "FAILED MISSIONS" )
                    };
                    if( cell.y < 3 ) {
                        if( const auto clicked = tab_input::index_at( {
                                .texts = tab_texts,
                                .current = static_cast<size_t>( tab ),
                                .max_width = getmaxx( w_missions ),
                                .x = cell.x,
                            } ) ) {
                            if( *clicked != static_cast<int>( tab ) ) {
                                tab = static_cast<tab_mode>( *clicked );
                                selection = 0;
                                mouse_row.reset();
                            }
                        }
                    } else if( const auto hit = scrollbar_input::click( {
                    .offset = point( 0, 3 ),
                    .viewport_size = entries_per_page,
                    .content_size = static_cast<int>( umissions.size() ),
                    .viewport_pos = static_cast<int>( selection ),
                    .scroll_to_last = true,
                               }, cell ) ) {
                        selection = static_cast<size_t>( hit->viewport_pos );
                        mouse_row.reset();
                    } else if( cell.x >= 1 && cell.x < 30 && cell.y >= 3 &&
                               cell.y < 3 + entries_per_page ) {
                        const size_t idx = entries_per_page * ( selection / entries_per_page ) +
                                           cell.y - 3;
                        if( idx < umissions.size() ) {
                            if( mouse_row && *mouse_row == idx ) {
                                // A second click on the same row runs the row's Enter
                                // action; confirming a mission keeps its usual flow.
                                action = "CONFIRM";
                                mouse_row.reset();
                            } else {
                                selection = idx;
                                mouse_row = idx;
                            }
                        }
                    }
                }
            } else {
                action.clear();
            }
        } else {
            // Keyboard navigation and content changes forget the pending row click.
            mouse_row.reset();
        }
        if( action == "RIGHT" ) {
            tab = static_cast<tab_mode>( static_cast<int>( tab ) + 1 );
            if( tab >= tab_mode::NUM_TABS ) {
                tab = tab_mode::FIRST_TAB;
            }
            selection = 0;
        } else if( action == "LEFT" ) {
            tab = static_cast<tab_mode>( static_cast<int>( tab ) - 1 );
            if( tab < tab_mode::FIRST_TAB ) {
                tab = tab_mode::LAST_TAB;
            }
            selection = 0;
        } else if( action == "DOWN" ) {
            selection++;
            if( selection >= umissions.size() ) {
                selection = 0;
            }
        } else if( action == "UP" ) {
            if( selection == 0 ) {
                selection = umissions.empty() ? 0 : umissions.size() - 1;
            } else {
                selection--;
            }
        } else if( action == "CONFIRM" ) {
            if( tab == tab_mode::TAB_ACTIVE && selection < umissions.size() ) {
                u.set_active_mission( *umissions[selection] );
            }
            break;
        } else if( action == "QUIT" ) {
            break;
        }
    }
}

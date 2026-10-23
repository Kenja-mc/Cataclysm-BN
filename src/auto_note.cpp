#include "auto_note.h"

#include "cata_utility.h"
#include "color.h"
#include "cursesdef.h"
#include "filesystem.h"
#include "fstream_utils.h"
#include "game.h"
#include "generic_factory.h"
#include "input.h"
#include "json.h"
#include "mapgen/map_extras.h"
#include "options.h"
#include "output.h"
#include "point.h"
#include "scrollbar_input.h"
#include "translations.h"
#include "ui_manager.h"
#include "world.h"

#include <iostream>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace auto_notes
{
void auto_note_settings::clear()
{
    autoNoteEnabled.clear();
}

bool auto_note_settings::save()
{
    world *world = g->get_active_world();
    if( !world->player_file_exist( ".sav" ) ) {
        return true;
    }

    return world->write_to_player_file( ".ano.json", [&]( std::ostream & fstr ) {
        JsonOut jout{ fstr, true };

        jout.start_object();

        jout.member( "enabled" );

        jout.start_array();
        for( const string_id<map_extra> &entry : autoNoteEnabled ) {
            jout.write( entry.str() );
        }
        jout.end_array();

        jout.member( "discovered" );

        jout.start_array();
        for( const string_id<map_extra> &entry : discovered ) {
            jout.write( entry.str() );
        }
        jout.end_array();

        jout.end_object();

    }, _( "auto notes configuration" ) );
}

void auto_note_settings::load()
{
    clear();

    const auto parseJson = [&]( JsonIn & jin ) {
        jin.start_object();

        while( !jin.end_object() ) {
            const std::string name = jin.get_member_name();

            if( name == "enabled" ) {
                jin.start_array();
                while( !jin.end_array() ) {
                    const std::string entry = jin.get_string();
                    autoNoteEnabled.insert( string_id<map_extra> {entry} );
                }
            } else if( name == "discovered" ) {
                jin.start_array();
                while( !jin.end_array() ) {
                    const std::string entry = jin.get_string();
                    discovered.insert( string_id<map_extra> {entry} );
                }
            } else {
                jin.skip_value();
            }

        }
    };

    if( !g->get_active_world()->read_from_player_file_json( ".ano.json", parseJson,
            true ) ) {
        default_initialize();
        save();
    }
}

void auto_note_settings::default_initialize()
{
    clear();

    for( auto &extra : MapExtras::mapExtraFactory().get_all() ) {
        if( extra.autonote ) {
            autoNoteEnabled.insert( extra.id );
        }
    }
}

void auto_note_settings::set_discovered( const string_id<map_extra> &mapExtId )
{
    discovered.insert( mapExtId );
}

bool auto_note_settings::was_discovered( const string_id<map_extra> &mapExtId ) const
{
    return discovered.contains( mapExtId );
}

void auto_note_settings::show_gui()
{
    auto_note_manager_gui gui{ };
    gui.show();

    if( gui.was_changed() ) {
        save();
    }
}

bool auto_note_settings::has_auto_note_enabled( const string_id<map_extra> &mapExtId ) const
{
    return autoNoteEnabled.contains( mapExtId );
}

void auto_note_settings::set_auto_note_status( const string_id<map_extra> &mapExtId,
        const bool enabled )
{
    if( enabled ) {
        autoNoteEnabled.insert( mapExtId );
    } else if( has_auto_note_enabled( mapExtId ) ) {
        autoNoteEnabled.erase( mapExtId );
    }
}

auto_note_manager_gui::auto_note_manager_gui()
{
    const auto_note_settings &settings = get_auto_notes_settings();

    for( auto &extra : MapExtras::mapExtraFactory().get_all() ) {
        // Ignore all extras that have autonote disabled in the JSON.
        // This filters out lots of extras users shouldn't see (like "normal")
        if( !extra.autonote ) {
            continue;
        }

        bool isAutoNoteEnabled = settings.has_auto_note_enabled( extra.id );

        mapExtraCache.emplace( extra.id, std::make_pair( extra,
                               isAutoNoteEnabled ) );

        if( settings.was_discovered( extra.id ) ) {
            displayCache.push_back( extra.id );
        }
    }
}

bool auto_note_manager_gui::was_changed() const
{
    return wasChanged;
}

void auto_note_manager_gui::show()
{
    const int iHeaderHeight = 3;
    int iContentHeight = 0;
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

    // ===========================================================================
    // If the display cache contains no entries, the player might not have discovered any of
    // the map extras. In this case, we switch to a special state that alerts the user of this
    // in order to avoid confusion a completely empty GUI might normally create.
    const bool emptyMode = displayCache.empty();
    const int cacheSize = static_cast<int>( displayCache.size() );

    int currentLine = 0;
    int startPosition = 0;
    int endPosition = 0;

    input_context ctx{ "AUTO_NOTES" };
    ctx.register_action( "QUIT" );
    ctx.register_action( "SWITCH_AUTO_NOTE_OPTION" );
    ctx.register_action( "HELP_KEYBINDINGS" );

    const auto modern = get_option<std::string>( "CONTROL_SCHEME" ) == "modern";
    if( modern ) {
        ctx.register_action( "COORDINATE" );
        ctx.register_action( "MOUSE_MOVE" );
        ctx.register_action( "SELECT" );
        ctx.register_action( "SEC_SELECT" );
        ctx.register_action( "SCROLL_UP" );
        ctx.register_action( "SCROLL_DOWN" );
    }

    if( !emptyMode ) {
        ctx.register_cardinal();
        ctx.register_action( "CONFIRM" );
        ctx.register_action( "QUIT" );
        ctx.register_action( "ENABLE_MAPEXTRA_NOTE" );
        ctx.register_action( "DISABLE_MAPEXTRA_NOTE" );
        ctx.register_action( "CHANGE_MAPEXTRA_CHARACTER" );
    }

    // Matches the draw_scrollbar() call in on_redraw below.
    const auto scrollbar_geometry = [&]() {
        return scrollbar_input::geometry{
            .offset = point( 0, 4 ),
            .viewport_size = iContentHeight,
            .content_size = cacheSize,
            .viewport_pos = currentLine,
            .scroll_to_last = true,
        };
    };
    // Header rectangles of the drawn shortcut labels.
    struct click_label {
        int x0 = 0;
        int x1 = 0;
        std::string action;
    };
    auto header_labels = std::vector<click_label>{};
    // Row of the last plain click, -1 when the next click starts a new pair.
    auto last_click_row = -1;
    // A row click leaves the view where it is, so a second click hits the same row.
    auto preserve_view = false;

    ui.on_redraw( [&]( const ui_adaptor & ) {
        // == Draw border
        draw_border( w_border, BORDER_COLOR, _( " AUTO NOTES MANAGER " ) );
        mvwputch( w_border, point( 0, 2 ), c_light_gray, LINE_XXXO );
        mvwputch( w_border, point( 79, 2 ), c_light_gray, LINE_XOXX );
        mvwputch( w_border, point( 61, FULL_SCREEN_HEIGHT - 1 ), c_light_gray, LINE_XXOX );
        wnoutrefresh( w_border );

        // == Draw header
        header_labels.clear();
        int tmpx = 0;
        const auto draw_label = [&]( const std::string & text, const std::string & action ) {
            const auto x0 = tmpx;
            tmpx += static_cast<int>( shortcut_print( w_header, point( x0, 0 ), c_white, c_light_green,
                                     text ) );
            header_labels.push_back( { .x0 = x0, .x1 = tmpx, .action = action } );
            tmpx += 2;
        };
        draw_label( _( "<E>nable" ), "ENABLE_MAPEXTRA_NOTE" );
        draw_label( _( "<D>isable" ), "DISABLE_MAPEXTRA_NOTE" );
        draw_label( _( "<Enter> - Toggle" ), "CONFIRM" );

        // Draw horizontal line and corner pieces of the table
        for( int x = 0; x < 78; x++ ) {
            if( x == 51 || x == 60 ) {
                mvwputch( w_header, point( x, 1 ), c_light_gray, LINE_OXXX );
                mvwputch( w_header, point( x, 2 ), c_light_gray, LINE_XOXO );
            } else {
                mvwputch( w_header, point( x, 1 ), c_light_gray, LINE_OXOX );
            }
        }

        mvwprintz( w_header, point( 1, 2 ), c_white, _( "Map Extra" ) );
        mvwprintz( w_header, point( 53, 2 ), c_white, _( "Symbol" ) );
        mvwprintz( w_header, point( 62, 2 ), c_white, _( "Enabled" ) );

        wnoutrefresh( w_header );

        mvwprintz( w_header, point( 39, 0 ), c_white, _( "Auto notes enabled:" ) );

        int currentX = 60;
        currentX += shortcut_print( w_header, point( currentX, 0 ),
                                    get_option<bool>( "AUTO_NOTES" ) ? c_light_green : c_light_red, c_white,
                                    get_option<bool>( "AUTO_NOTES" ) ? _( "True" ) : _( "False" ) );

        currentX += shortcut_print( w_header, point( currentX, 0 ), c_white, c_light_green, "  " );
        const auto switch_x0 = currentX;
        const auto switch_len = static_cast<int>( shortcut_print( w_header, point( currentX, 0 ), c_white,
                                  c_light_green, _( "<S>witch " ) ) );
        header_labels.push_back( { .x0 = switch_x0, .x1 = switch_x0 + switch_len,
                                   .action = "SWITCH_AUTO_NOTE_OPTION" } );

        // Clear table
        for( int y = 0; y < iContentHeight; y++ ) {
            for( int x = 0; x < 79; x++ ) {
                // The middle beams needs special treatment
                if( x == 51 || x == 60 ) {
                    mvwputch( w, point( x, y ), c_light_gray, LINE_XOXO );
                } else {
                    mvwputch( w, point( x, y ), c_black, ' ' );
                }
            }
        }

        const auto sb = scrollbar_geometry();
        draw_scrollbar( w_border, sb.viewport_pos, sb.viewport_size, sb.content_size, sb.offset );

        if( emptyMode ) {
            // NOLINTNEXTLINE(cata-use-named-point-constants)
            mvwprintz( w, point( 1, 0 ), c_light_gray,
                       _( "Discover more special encounters to populate this list" ) );
        } else {
            if( preserve_view ) {
                if( startPosition > currentLine ) {
                    startPosition = currentLine;
                }
                if( currentLine >= startPosition + iContentHeight ) {
                    startPosition = currentLine - iContentHeight + 1;
                }
            } else {
                calcStartPos( startPosition, currentLine, iContentHeight, displayCache.size() );
            }
            endPosition = startPosition + ( iContentHeight > cacheSize ? cacheSize : iContentHeight );

            for( int i = startPosition; i < endPosition; ++i ) {
                const string_id<map_extra> &displayCacheEntry = displayCache[i];
                const auto &cacheEntry = mapExtraCache[displayCacheEntry];

                const auto lineColor = ( i == currentLine ) ? hilite( c_white ) : c_white;
                const auto statusColor = cacheEntry.second ? c_green : c_red;
                const auto statusString = cacheEntry.second ?
                                          pgettext( "auto notes status value", "yes" ) :
                                          pgettext( "auto notes status value", "no" );
                const auto charColor = cacheEntry.first.color;
                const auto displayChar = cacheEntry.first.get_symbol();

                mvwprintz( w, point( 1, i - startPosition ), lineColor, "" );

                if( i == currentLine ) {
                    wprintz( w, c_yellow, ">> " );
                } else {
                    wprintz( w, c_yellow, "   " );
                }

                wprintz( w, lineColor, "%s", cacheEntry.first.name() );

                // Print the character this map extra is indicated by on the map
                mvwprintz( w, point( 55, i - startPosition ), charColor, "%s", displayChar );
                // Since yes is longer than no, we need to clear the space for the status string before
                // displaying the current text. Otherwise artifacts might occur.
                mvwprintz( w, point( 64, i - startPosition ), statusColor, "     " );
                mvwprintz( w, point( 64, i - startPosition ), statusColor, "%s", statusString );
            }
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
                    last_click_row = -1;
                    preserve_view = false;
                    consumed = true;
                }
            }
            if( !consumed ) {
                if( const auto header_cell = cell_in( w_header ) ) {
                    if( header_cell->y == 0 ) {
                        for( const auto &label : header_labels ) {
                            if( header_cell->x >= label.x0 && header_cell->x < label.x1 ) {
                                currentAction = label.action;
                                last_click_row = -1;
                                preserve_view = false;
                                consumed = true;
                                break;
                            }
                        }
                    }
                } else if( !emptyMode ) {
                    if( const auto cell = cell_in( w ) ) {
                        const auto row = startPosition + cell->y;
                        if( cell->y < iContentHeight && row < cacheSize ) {
                            if( row == last_click_row ) {
                                // The second click on the same row runs Enter.
                                currentAction = "CONFIRM";
                                last_click_row = -1;
                                preserve_view = false;
                            } else {
                                currentLine = row;
                                last_click_row = row;
                                preserve_view = true;
                            }
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

        // Actions that also work with no items to display
        if( currentAction == "SWITCH_AUTO_NOTE_OPTION" ) {
            get_options().get_option( "AUTO_NOTES" ).setNext();

            if( get_option<bool>( "AUTO_NOTES" ) && !get_option<bool>( "AUTO_NOTES_MAP_EXTRAS" ) ) {
                get_options().get_option( "AUTO_NOTES_MAP_EXTRAS" ).setNext();
            }

            get_options().save();
        } else if( currentAction == "QUIT" ) {
            break;
        }

        if( emptyMode ) {
            continue;
        }

        const string_id<map_extra> &currentItem = displayCache[currentLine];
        std::pair<const map_extra, bool> &entry = mapExtraCache[currentItem];

        if( currentAction == "UP" || currentAction == "SCROLL_UP" ) {
            if( currentLine > 0 ) {
                --currentLine;
            } else {
                currentLine = cacheSize - 1;
            }
        } else if( currentAction == "DOWN" || currentAction == "SCROLL_DOWN" ) {
            if( currentLine == cacheSize - 1 ) {
                currentLine = 0;
            } else {
                ++currentLine;
            }
        }  else if( currentAction == "ENABLE_MAPEXTRA_NOTE" ) {
            entry.second = true;
            wasChanged = true;
        } else if( currentAction == "DISABLE_MAPEXTRA_NOTE" ) {
            entry.second = false;
            wasChanged = true;
        } else if( currentAction == "CONFIRM" ) {
            entry.second = !entry.second;
            wasChanged = true;
        }
    }

    if( !was_changed() ) {
        return;
    }

    if( query_yn( _( "Save changes?" ) ) ) {
        auto_notes::auto_note_settings &settings = get_auto_notes_settings();

        for( const auto &entry : mapExtraCache ) {
            settings.set_auto_note_status( entry.second.first.id, entry.second.second );
        }
    }
}
} // namespace auto_notes

auto_notes::auto_note_settings &get_auto_notes_settings()
{
    static auto_notes::auto_note_settings staticSettings;
    return staticSettings;
}

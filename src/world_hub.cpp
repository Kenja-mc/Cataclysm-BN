#include "world_hub.h"

#include <algorithm>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "catacharset.h"
#include "color.h"
#include "cursesdef.h"
#include "debug.h"
#include "input.h"
#include "options.h"
#include "output.h"
#include "panels.h"
#include "point.h"
#include "string_formatter.h"
#include "tab_input.h"
#include "translations.h"
#include "ui.h"
#include "ui_manager.h"

namespace
{
constexpr int max_numbered_tabs = 9;
constexpr int strip_height = 3;

class page_host : public world_hub::host
{
    public:
        page_host( bool &visible, ui_adaptor &ui ) : visible_( visible ), ui_( ui ) {}

        auto hide() -> void override {
            visible_ = false;
            ui_.mark_resize();
        }
        auto restore() -> void override {
            visible_ = true;
            ui_.mark_resize();
        }

    private:
        bool &visible_;
        ui_adaptor &ui_;
};
}

auto world_hub::show( std::vector<panel_ptr> screens, const size_t start_tab ) -> void
{
    if( screens.empty() ) {
        return;
    }
    if( screens.size() > static_cast<size_t>( max_numbered_tabs ) ) {
        debugmsg( "The World page can number only %d tabs; %d are hidden.",
                  max_numbered_tabs, static_cast<int>( screens.size() ) );
    }
    const int count = std::min( static_cast<int>( screens.size() ), max_numbered_tabs );
    screens.resize( static_cast<size_t>( count ) );

    const bool modern = get_option<std::string>( "CONTROL_SCHEME" ) == "modern";

    input_context ctxt( "WORLD_HUB" );
    ctxt.register_cardinal();
    ctxt.register_action( "CONFIRM" );
    ctxt.register_action( "QUIT" );
    ctxt.register_action( "PREV_TAB" );
    ctxt.register_action( "NEXT_TAB" );
    ctxt.register_action( "PAGE_UP" );
    ctxt.register_action( "PAGE_DOWN" );
    ctxt.register_action( "HELP_KEYBINDINGS" );
    ctxt.register_action( "ANY_INPUT" );
    if( modern ) {
        ctxt.register_action( "COORDINATE" );
        ctxt.register_action( "MOUSE_MOVE" );
        ctxt.register_action( "SELECT" );
        ctxt.register_action( "SEC_SELECT" );
        ctxt.register_action( "SCROLL_UP" );
        ctxt.register_action( "SCROLL_DOWN" );
    }

    std::vector<std::string> labels;
    labels.reserve( static_cast<size_t>( count ) );
    for( int i = 0; i < count; ++i ) {
        labels.push_back( string_format( "%d %s", i + 1, screens[i]->name() ) );
    }

    size_t current = std::min( start_tab, static_cast<size_t>( count ) - 1 );
    bool visible = true;
    catacurses::window page;
    catacurses::window body;

    ui_adaptor ui;
    page_host host( visible, ui );
    const auto init_windows = [&]( ui_adaptor & ui ) {
        if( !visible ) {
            ui.position( point_zero, point_zero );
            return;
        }
        const int page_height = std::min( strip_height + FULL_SCREEN_HEIGHT + 1, TERMY - 2 );
        page = new_centered_win( page_height, FULL_SCREEN_WIDTH );
        const int body_height = std::max( 5, std::min( FULL_SCREEN_HEIGHT,
                                          getmaxy( page ) - strip_height - 1 ) );
        body = catacurses::newwin( body_height, std::min( FULL_SCREEN_WIDTH, getmaxx( page ) ),
                                   point( getbegx( page ), getbegy( page ) + strip_height ) );
        ui.position_from_window( page );
    };
    ui.on_screen_resize( init_windows );
    init_windows( ui );

    ui.on_redraw( [&]( const ui_adaptor & ) {
        if( !visible ) {
            return;
        }
        werase( page );
        draw_tabs( page, labels, current );
        const std::string footer = string_format(
                                       _( "1-%d or %s/%s switch tabs, %s changes inner pages, %s returns to play." ),
                                       count, ctxt.get_desc( "LEFT", 1 ), ctxt.get_desc( "RIGHT", 1 ),
                                       ctxt.get_desc( "NEXT_TAB", 1 ), ctxt.get_desc( "QUIT", 1 ) );
        mvwprintz( page, point( 2, getmaxy( page ) - 1 ), c_dark_gray, footer );
        wnoutrefresh( page );

        screens[current]->draw( body, ctxt );
    } );

    bool done = false;
    while( !done ) {
        screens[current]->refresh();
        ui_manager::redraw();
        const std::string action = ctxt.handle_input();
        const input_event event = ctxt.get_raw_input();

        if( event.type == input_event_t::keyboard && event.sequence.size() == 1 ) {
            const int key = event.get_first_input();
            if( key >= '1' && key - '1' < count ) {
                current = static_cast<size_t>( key - '1' );
                continue;
            }
        }
        if( action == "QUIT" ) {
            for( panel_ptr &screen : screens ) {
                screen->close();
            }
            done = true;
            continue;
        }
        if( action == "LEFT" ) {
            current = ( current + static_cast<size_t>( count ) - 1 ) % static_cast<size_t>( count );
            continue;
        }
        if( action == "RIGHT" ) {
            current = ( current + 1 ) % static_cast<size_t>( count );
            continue;
        }
        if( modern && action == "SELECT" ) {
            if( const auto mouse = ctxt.get_coordinates( page ) ) {
                const point cell = mouse->xy().raw() + point( getmaxx( page ), getmaxy( page ) ) / 2;
                if( cell.y < strip_height ) {
                    if( const auto clicked = tab_input::index_at( {
                    .texts = labels,
                    .current = current,
                    .max_width = getmaxx( page ),
                    .x = cell.x,
                } ) ) {
                        current = static_cast<size_t>( *clicked );
                    }
                    continue;
                }
            }
        }
        screens[current]->handle( action, ctxt, body, host );
    }
}

namespace
{
auto draw_sidebar_strip( const catacurses::window &w, const std::vector<std::string> &labels,
                         const size_t current ) -> void
{
    auto at = point( 1, 0 );
    for( size_t i = 0; i < labels.size(); ++i ) {
        const auto label = " " + labels[i] + " ";
        if( at.x + utf8_width( label ) > getmaxx( w ) && at.x > 1 ) {
            at = point( 1, at.y + 1 );
        }
        if( at.y >= 2 ) {
            break;
        }
        mvwprintz( w, at, i == current ? hilite( c_white ) : c_dark_gray, label );
        at.x += utf8_width( label ) + 1;
    }
}
}

auto world_hub::show_in_sidebar( std::vector<panel_ptr> screens ) -> void
{
    if( screens.empty() ) {
        return;
    }
    auto &mgr = panel_manager::get_manager();
    const bool right = get_option<std::string>( "SIDEBAR_POSITION" ) == "right";
    const int width = right ? mgr.get_width_right() : mgr.get_width_left();
    if( width < 24 ) {
        show( std::move( screens ) );
        return;
    }
    const int count = std::min( static_cast<int>( screens.size() ), max_numbered_tabs );
    screens.resize( static_cast<size_t>( count ) );

    static auto remembered = size_t( 0 );
    auto current = std::min( remembered, static_cast<size_t>( count ) - 1 );

    input_context ctxt( "WORLD_HUB" );
    ctxt.register_cardinal();
    ctxt.register_action( "CONFIRM" );
    ctxt.register_action( "QUIT" );
    ctxt.register_action( "PREV_TAB" );
    ctxt.register_action( "NEXT_TAB" );
    ctxt.register_action( "PAGE_UP" );
    ctxt.register_action( "PAGE_DOWN" );
    ctxt.register_action( "HELP_KEYBINDINGS" );
    ctxt.register_action( "ANY_INPUT" );

    auto labels = std::vector<std::string>();
    for( int i = 0; i < count; ++i ) {
        labels.push_back( string_format( "%d %s", i + 1, screens[i]->name() ) );
    }

    auto details = std::optional<size_t>();
    constexpr int side_strip = 2;
    const auto origin = point( right ? TERMX - width : 0, 0 );
    {
        catacurses::window page;
        catacurses::window body;
        bool visible = true;
        ui_adaptor ui;
        page_host host( visible, ui );
        const auto init_windows = [&]( ui_adaptor & ui ) {
            if( !visible ) {
                ui.position( point_zero, point_zero );
                return;
            }
            page = catacurses::newwin( TERMY, width, origin );
            body = catacurses::newwin( std::max( 1, TERMY - side_strip - 1 ), width,
                                       origin + point( 0, side_strip ) );
            ui.position_from_window( page );
        };
        ui.on_screen_resize( init_windows );
        init_windows( ui );

        ui.on_redraw( [&]( const ui_adaptor & ) {
            if( !visible ) {
                return;
            }
            werase( page );
            draw_sidebar_strip( page, labels, current );
            mvwprintz( page, point( 1, getmaxy( page ) - 1 ), c_dark_gray,
                       string_format( _( "%s details  %s play" ), ctxt.get_desc( "CONFIRM", 1 ),
                                      ctxt.get_desc( "QUIT", 1 ) ) );
            wnoutrefresh( page );
            screens[current]->draw( body, ctxt );
        } );

        bool done = false;
        while( !done ) {
            screens[current]->refresh();
            ui_manager::redraw();
            const std::string action = ctxt.handle_input();
            const input_event event = ctxt.get_raw_input();
            if( event.type == input_event_t::keyboard && event.sequence.size() == 1 ) {
                const int key = event.get_first_input();
                if( key >= '1' && key - '1' < count ) {
                    current = static_cast<size_t>( key - '1' );
                    continue;
                }
            }
            if( action == "QUIT" ) {
                done = true;
                continue;
            }
            if( action == "CONFIRM" ) {
                details = current;
                done = true;
                continue;
            }
            if( action == "LEFT" ) {
                current = ( current + static_cast<size_t>( count ) - 1 ) % static_cast<size_t>( count );
                continue;
            }
            if( action == "RIGHT" ) {
                current = ( current + 1 ) % static_cast<size_t>( count );
                continue;
            }
            screens[current]->handle( action, ctxt, body, host );
        }
    }

    remembered = current;
    if( details ) {
        show( std::move( screens ), *details );
        return;
    }
    for( panel_ptr &screen : screens ) {
        screen->close();
    }
}

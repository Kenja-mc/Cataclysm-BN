#include "world_hub.h"

#include <algorithm>
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
#include "point.h"
#include "string_formatter.h"
#include "tab_input.h"
#include "translations.h"
#include "ui.h"
#include "ui_manager.h"

namespace
{
/// The digits 1-9 on the tab strip limit how many tabs one page can number.
constexpr int max_numbered_tabs = 9;
/// Rows above the panel body used by the numbered tab strip (see draw_tabs).
constexpr int strip_height = 3;

/// Lets a panel hide the page while a look_around-style modal needs the map.
class page_host : public world_hub::host
{
    public:
        page_host( bool &visible, ui_adaptor &ui ) : visible_( visible ), ui_( ui ) {}

        void hide() override {
            visible_ = false;
            ui_.mark_resize();
        }
        void restore() override {
            visible_ = true;
            ui_.mark_resize();
        }

    private:
        bool &visible_;
        ui_adaptor &ui_;
};
} // namespace

auto world_hub::show( std::vector<panel_ptr> screens ) -> void
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
    // Panel-only keys (the zone actions, SWAPTONPC) arrive as ANY_INPUT here; the panel that
    // owns them translates them with its own screen's context.
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

    size_t current = 0;
    bool visible = true;
    catacurses::window page;
    catacurses::window body;

    ui_adaptor ui;
    page_host host( visible, ui );
    const auto init_windows = [&]( ui_adaptor &ui ) {
        if( !visible ) {
            ui.position( point_zero, point_zero );
            return;
        }
        // Leave the screen's last row to the menu keyhints, as the other full-screen pages do.
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

        // Number keys choose a tab even where the scheme also uses that digit to move.
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
                // Only the strip is the page's; every click below it belongs to the panel.
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

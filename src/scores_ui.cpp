#include "scores_ui.h"

#include <algorithm>
#include <cassert>
#include <iterator>
#include <memory>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

#include "achievement.h"
#include "catacharset.h"
#include "color.h"
#include "cursesdef.h"
#include "event_statistics.h"
#include "input.h"
#include "kill_tracker.h"
#include "options.h"
#include "output.h"
#include "point.h"
#include "scrollbar_input.h"
#include "stats_tracker.h"
#include "translations.h"
#include "ui.h"
#include "ui_manager.h"
#include "world_hub.h"

static std::string get_achievements_text( const achievements_tracker &achievements )
{
    std::string os;
    std::vector<const achievement *> valid_achievements = achievements.valid_achievements();
    valid_achievements.erase(
        std::remove_if( valid_achievements.begin(), valid_achievements.end(),
    [&]( const achievement * a ) {
        return achievements.is_hidden( a );
    } ), valid_achievements.end() );
    using sortable_achievement =
        std::tuple<achievement_completion, std::string, const achievement *>;
    std::vector<sortable_achievement> sortable_achievements;
    std::transform( valid_achievements.begin(), valid_achievements.end(),
                    std::back_inserter( sortable_achievements ),
    [&]( const achievement * ach ) {
        achievement_completion comp = achievements.is_completed( ach->id );
        return std::make_tuple( comp, ach->name().translated(), ach );
    } );
    std::sort( sortable_achievements.begin(), sortable_achievements.end(), localized_compare );
    for( const sortable_achievement &ach : sortable_achievements ) {
        os += achievements.ui_text_for( std::get<const achievement *>( ach ) ) + "\n";
    }
    if( valid_achievements.empty() ) {
        os += _( "This game has no valid achievements.\n" );
    }
    os += _( "Note that only achievements that existed when you started this game and still "
             "exist now will appear here." );
    return os;
}

static std::string get_scores_text( stats_tracker &stats )
{
    std::string os;
    std::vector<const score *> valid_scores = stats.valid_scores();
    for( const score *scr : valid_scores ) {
        os += scr->description( stats ) + "\n";
    }
    if( valid_scores.empty() ) {
        os += _( "This game has no valid scores.\n" );
    }
    os += _( "\nNote that only scores that existed when you started this game and still exist now "
             "will appear here." );
    return os;
}

namespace
{
/// Number of text lines one mouse wheel notch scrolls in these text panes.
constexpr auto wheel_text_lines = 3;

/// x start of each drawn tab, -1 when a tab is scrolled off. Mirrors the placement loop of
/// draw_tabs() so click targets cover exactly the rendered tab labels, including its
/// three-column spacing after each label.
auto tab_positions( const catacurses::window &w, const std::vector<std::string> &tab_texts,
                    size_t current_tab ) -> std::vector<int>
{
    constexpr auto tab_step = 3;
    const auto max_tab_width = getmaxx( w );

    auto total_used_width = 0;
    auto current = 0;
    for( size_t i = 0; i < tab_texts.size(); ++i ) {
        total_used_width += utf8_width( tab_texts[i] ) + tab_step;
        if( i == current_tab ) {
            current = total_used_width;
        }
    }
    auto start = 0;
    calcStartPos( start, current, max_tab_width, total_used_width );

    auto start_i = size_t{ 0 };
    if( start != 0 ) {
        current = 0;
        for( size_t i = 0; i < tab_texts.size(); ++i ) {
            current += utf8_width( tab_texts[i] ) + tab_step;
            if( current >= start ) {
                start_i = i + 1;
                break;
            }
        }
    }

    std::vector<int> xs( tab_texts.size(), -1 );
    auto x = 2;
    for( size_t i = start_i; i < tab_texts.size(); ++i ) {
        const auto newx = x + utf8_width( tab_texts[i] ) + tab_step;
        if( newx <= max_tab_width ) {
            xs[i] = x;
        }
        x = newx;
    }
    return xs;
}

/// Registers the mouse actions the modern control scheme answers in these screens.
auto register_modern_mouse( input_context &ctxt ) -> void
{
    ctxt.register_action( "COORDINATE" );
    ctxt.register_action( "MOUSE_MOVE" );
    ctxt.register_action( "SELECT" );
    ctxt.register_action( "SCROLL_UP" );
    ctxt.register_action( "SCROLL_DOWN" );
}

/// A scrollbar click on the shared scrolling text pane. Returns true when the click was on the
/// drawn scrollbar and moved the view.
auto handle_text_view_mouse( scrolling_text_view &view, const input_context &ctxt,
                             const catacurses::window &w_view ) -> bool
{
    const auto mouse = ctxt.get_coordinates( w_view );
    if( !mouse ) {
        return false;
    }
    const auto cell = mouse->xy().raw() + point( getmaxx( w_view ), getmaxy( w_view ) ) / 2;
    const auto hit = scrollbar_input::click( {
        .offset = point( 0, 0 ),
        .viewport_size = getmaxy( w_view ),
        .content_size = view.num_lines(),
        .viewport_pos = view.offset(),
        .scroll_to_last = false,
    }, cell );
    if( !hit ) {
        return false;
    }
    view.scroll_to( hit->viewport_pos );
    return true;
}

/// The achievements/scores/kills text screen, shared by the standalone screen and the World
/// page's Scores tab. It owns the inner tab strip and the scrolling pane.
class scores_view
{
    public:
        scores_view( const achievements_tracker &achievements, stats_tracker &stats,
                     const kill_tracker &kills )
            : achievements_( achievements ), stats_( stats ), kills_( kills ) {}

        void draw( const catacurses::window &w );
        /// Returns true when the screen should close.
        auto handle( std::string action, input_context &ctxt, const catacurses::window &w,
                     bool modern ) -> bool;

    private:
        enum class tab_mode {
            achievements,
            scores,
            kills,
            num_tabs,
            first_tab = achievements,
        };

        void prepare_view( const catacurses::window &w );
        auto tab_texts() const -> std::vector<std::string>;

        const achievements_tracker &achievements_;
        stats_tracker &stats_;
        const kill_tracker &kills_;
        tab_mode tab = tab_mode::first_tab;
        bool new_tab = true;
        catacurses::window w_view;
        scrolling_text_view view{ w_view };
        std::vector<std::pair<tab_mode, std::string>> tabs = {
            { tab_mode::achievements, _( "ACHIEVEMENTS" ) },
            { tab_mode::scores, _( "SCORES" ) },
            { tab_mode::kills, _( "KILLS" ) },
        };
};

auto scores_view::tab_texts() const -> std::vector<std::string>
{
    std::vector<std::string> texts;
    texts.reserve( tabs.size() );
    for( const auto &tab_pair : tabs ) {
        texts.push_back( tab_pair.second );
    }
    return texts;
}

void scores_view::prepare_view( const catacurses::window &w )
{
    const int height = getmaxy( w ) - 4;
    const int width = getmaxx( w ) - 1;
    const point origin( getbegx( w ), getbegy( w ) + 3 );
    if( !w_view || getmaxy( w_view ) != height || getmaxx( w_view ) != width ||
        getbegx( w_view ) != origin.x || getbegy( w_view ) != origin.y ) {
        w_view = catacurses::newwin( height, width, origin );
        // The pane below the tabs moved, so the wrapped text has to be built again.
        new_tab = true;
    }
}

void scores_view::draw( const catacurses::window &w )
{
    prepare_view( w );
    if( new_tab ) {
        switch( tab ) {
            case tab_mode::achievements:
                view.set_text( get_achievements_text( achievements_ ) );
                break;
            case tab_mode::scores:
                view.set_text( get_scores_text( stats_ ) );
                break;
            case tab_mode::kills:
                view.set_text( kills_.get_kills_text() );
                break;
            case tab_mode::num_tabs:
                assert( false );
                break;
        }
        new_tab = false;
    }

    werase( w );
    draw_tabs( w, tabs, tab );
    draw_border_below_tabs( w );
    wnoutrefresh( w );

    view.draw( c_white );
}

auto scores_view::handle( std::string action, input_context &ctxt, const catacurses::window &w,
                          bool modern ) -> bool
{
    const auto event = ctxt.get_raw_input();
    if( modern && event.type == input_event_t::mouse && action == "SELECT" ) {
        if( const auto mouse = ctxt.get_coordinates( w ) ) {
            const auto cell = mouse->xy().raw() + point( getmaxx( w ), getmaxy( w ) ) / 2;
            if( cell.y >= 0 && cell.y <= 1 ) {
                // The tab labels are the only clickable part of the tab strip.
                const auto texts = tab_texts();
                const auto xs = tab_positions( w, texts, static_cast<size_t>( tab ) );
                for( size_t i = 0; i < tabs.size(); ++i ) {
                    if( xs[i] >= 0 && cell.x >= xs[i] &&
                        cell.x < xs[i] + utf8_width( texts[i] ) + 3 ) {
                        tab = tabs[i].first;
                        new_tab = true;
                        break;
                    }
                }
                return false;
            }
            handle_text_view_mouse( view, ctxt, w_view );
        }
        return false;
    }
    // The World page owns Left/Right for its outer tabs; inside it the panel uses Tab keys.
    if( action == "NEXT_TAB" ) {
        action = "RIGHT";
    } else if( action == "PREV_TAB" ) {
        action = "LEFT";
    }
    if( action == "RIGHT" ) {
        tab = static_cast<tab_mode>( static_cast<int>( tab ) + 1 );
        if( tab >= tab_mode::num_tabs ) {
            tab = tab_mode::first_tab;
        }
        new_tab = true;
    } else if( action == "LEFT" ) {
        tab = static_cast<tab_mode>( static_cast<int>( tab ) - 1 );
        if( tab < tab_mode::first_tab ) {
            tab = static_cast<tab_mode>( static_cast<int>( tab_mode::num_tabs ) - 1 );
        }
        new_tab = true;
    } else if( action == "DOWN" ) {
        view.scroll_down();
    } else if( action == "UP" ) {
        view.scroll_up();
    } else if( action == "SCROLL_DOWN" ) {
        view.scroll_to( view.offset() + wheel_text_lines );
    } else if( action == "SCROLL_UP" ) {
        view.scroll_to( view.offset() - wheel_text_lines );
    } else if( action == "PAGE_DOWN" ) {
        view.page_down();
    } else if( action == "PAGE_UP" ) {
        view.page_up();
    } else if( action == "CONFIRM" || action == "QUIT" ) {
        return true;
    }
    return false;
}

class scores_panel : public world_hub::panel
{
    public:
        scores_panel( const achievements_tracker &achievements, stats_tracker &stats,
                      const kill_tracker &kills )
            : view( achievements, stats, kills ) {}

        auto name() const -> std::string override {
            return _( "Scores" );
        }
        void draw( const catacurses::window &body, input_context & ) override {
            view.draw( body );
        }
        void handle( const std::string &action, input_context &ctxt,
                     const catacurses::window &body, world_hub::host & ) override {
            view.handle( action, ctxt, body,
                         get_option<std::string>( "CONTROL_SCHEME" ) == "modern" );
        }

    private:
        scores_view view;
};

} // namespace

auto world_hub::scores_screen( const achievements_tracker &achievements, stats_tracker &stats,
                               const kill_tracker &kills ) -> panel_ptr
{
    return std::make_unique<scores_panel>( achievements, stats, kills );
}

void show_scores_ui( const achievements_tracker &achievements, stats_tracker &stats,
                     const kill_tracker &kills )
{
    scores_view view( achievements, stats, kills );
    catacurses::window w;

    input_context ctxt( "SCORES" );
    ctxt.register_cardinal();
    ctxt.register_action( "PAGE_UP" );
    ctxt.register_action( "PAGE_DOWN" );
    ctxt.register_action( "QUIT" );
    ctxt.register_action( "PREV_TAB" );
    ctxt.register_action( "NEXT_TAB" );
    ctxt.register_action( "HELP_KEYBINDINGS" );
    const auto modern = get_option<std::string>( "CONTROL_SCHEME" ) == "modern";
    if( modern ) {
        register_modern_mouse( ctxt );
    }

    ui_adaptor ui;
    const auto &init_windows = [&]( ui_adaptor & ui ) {
        w = new_centered_win( TERMY - 2, FULL_SCREEN_WIDTH );
        ui.position_from_window( w );
    };
    ui.on_screen_resize( init_windows );
    // initialize explicitly here since the view's window is created from this one
    init_windows( ui );

    ui.on_redraw( [&]( const ui_adaptor & ) {
        view.draw( w );
    } );

    bool done = false;
    while( !done ) {
        ui_manager::redraw();
        const std::string action = ctxt.handle_input();
        done = view.handle( action, ctxt, w, modern );
    }
}

void show_kills( kill_tracker &kills )
{
    catacurses::window w;

    input_context ctxt( "SCORES" );
    ctxt.register_cardinal();
    ctxt.register_action( "PAGE_UP" );
    ctxt.register_action( "PAGE_DOWN" );
    ctxt.register_action( "QUIT" );
    ctxt.register_action( "HELP_KEYBINDINGS" );
    const auto modern = get_option<std::string>( "CONTROL_SCHEME" ) == "modern";
    if( modern ) {
        register_modern_mouse( ctxt );
    }

    catacurses::window w_view;
    scrolling_text_view view( w_view );

    ui_adaptor ui;
    const auto &init_windows = [&]( ui_adaptor & ui ) {
        w = new_centered_win( TERMY - 2, FULL_SCREEN_WIDTH );
        w_view = catacurses::newwin( getmaxy( w ) - 4, getmaxx( w ) - 1,
                                     point( getbegx( w ), getbegy( w ) + 3 ) );
        ui.position_from_window( w );
        view.set_text( kills.get_kills_text() );
    };
    ui.on_screen_resize( init_windows );
    // initialize explicitly here since w_view is used before first redraw
    init_windows( ui );

    ui.on_redraw( [&]( const ui_adaptor & ) {
        werase( w );
        draw_border( w );
        wnoutrefresh( w );
        view.draw( c_white );
    } );

    while( true ) {
        ui_manager::redraw();
        const std::string action = ctxt.handle_input();
        const auto event = ctxt.get_raw_input();
        if( modern && event.type == input_event_t::mouse && action == "SELECT" ) {
            handle_text_view_mouse( view, ctxt, w_view );
            continue;
        }
        if( action == "DOWN" ) {
            view.scroll_down();
        } else if( action == "UP" ) {
            view.scroll_up();
        } else if( action == "SCROLL_DOWN" ) {
            view.scroll_to( view.offset() + wheel_text_lines );
        } else if( action == "SCROLL_UP" ) {
            view.scroll_to( view.offset() - wheel_text_lines );
        } else if( action == "PAGE_DOWN" ) {
            view.page_down();
        } else if( action == "PAGE_UP" ) {
            view.page_up();
        } else if( action == "CONFIRM" || action == "QUIT" ) {
            break;
        }
    }
}

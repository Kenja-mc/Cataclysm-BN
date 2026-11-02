#include "hud_draw.h"

#include <algorithm>
#include <vector>

#include "catacharset.h"
#include "output.h"

namespace hud_draw
{

namespace
{

auto windows = std::vector<catacurses::window>();
auto used = size_t{ 0 };

}

auto begin_frame() -> void { used = 0; }

auto panel( const canvas &area, const rect &r ) -> catacurses::window
{
    const auto at = point( std::clamp( r.at.x, 0, std::max( 0, area.width - 1 ) ),
                           std::clamp( r.at.y, 0, std::max( 0, area.height - 1 ) ) );
    const auto w = std::max( 1, std::min( r.width, area.width - at.x ) );
    const auto h = std::max( 1, std::min( r.height, area.height - at.y ) );
    const auto origin = area.origin + at;
    if( used == windows.size() ) {
        windows.emplace_back();
    }
    auto &win = windows[used++];
    if( !win || getmaxx( win ) != w || getmaxy( win ) != h || getbegx( win ) != origin.x ||
        getbegy( win ) != origin.y ) {
        win = catacurses::newwin( h, w, origin );
    }
    werase( win );
    return win;
}

auto end_frame() -> void
{
    for( auto i = size_t{ 0 }; i < used; ++i ) {
        wnoutrefresh( windows[i] );
    }
}

auto card( const catacurses::window &w, const card_options &opts ) -> void
{
    const auto wd = getmaxx( w );
    const auto ht = getmaxy( w );
    if( wd < 2 || ht < 2 ) {
        return;
    }
    hline( w, point( 1, 0 ), wd - 2, pal::border() );
    hline( w, point( 1, ht - 1 ), wd - 2, pal::border() );
    vline( w, point( 0, 1 ), ht - 2, pal::border() );
    vline( w, point( wd - 1, 1 ), ht - 2, pal::border() );
    mvwprintz( w, point_zero, pal::border(), "╭" );
    mvwprintz( w, point( wd - 1, 0 ), pal::border(), "╮" );
    mvwprintz( w, point( 0, ht - 1 ), pal::border(), "╰" );
    mvwprintz( w, point( wd - 1, ht - 1 ), pal::border(), "╯" );
    if( !opts.title.empty() ) {
        const auto x = text( w, point( 2, 0 ), pal::heading(), " " + opts.title + " " );
        if( !opts.summary.empty() ) {
            text( w, point( x, 0 ), opts.summary_color, opts.summary + " " );
        }
    }
}

auto rule( const catacurses::window &w, const rule_options &opts ) -> void
{
    hline( w, point( 1, opts.y ), getmaxx( w ) - 1, pal::border() );
    mvwprintz( w, point( 0, opts.y ), pal::border(), "├" );
    const auto x = text( w, point( 2, opts.y ), pal::heading(), " " + opts.title + " " );
    if( !opts.summary.empty() ) {
        text( w, point( x, opts.y ), opts.summary_color, opts.summary + " " );
    }
}

auto bar( const catacurses::window &w, const bar_options &opts ) -> void
{
    const auto max = std::max( 1, opts.max );
    const auto halves = std::clamp( opts.value, 0, max ) * opts.width * 2 / max;
    for( auto i = 0; i < opts.width; ++i ) {
        const auto filled = halves - i * 2;
        mvwprintz( w, opts.at + point( i, 0 ), filled >= 1 ? opts.fill : pal::border(),
                   filled >= 2 ? "█" : filled == 1 ? "▓" : "░" );
    }
}

auto text( const catacurses::window &w, const point at, const nc_color color,
           const std::string &s ) -> int
{
    const auto room = getmaxx( w ) - at.x;
    if( room <= 0 || at.y < 0 || at.y >= getmaxy( w ) ) {
        return at.x;
    }
    trim_and_print( w, at, room, color, s );
    return at.x + std::min( room, width( s ) );
}

auto dot( const catacurses::window &w, const point at ) -> int
{
    return text( w, at, pal::muted(), std::string( " " ) + glyph::dot + " " );
}

auto hline( const catacurses::window &w, const point at, const int width,
            const nc_color color ) -> void
{
    for( auto i = 0; i < width; ++i ) {
        mvwprintz( w, at + point( i, 0 ), color, "─" );
    }
}

auto vline( const catacurses::window &w, const point at, const int height,
            const nc_color color ) -> void
{
    for( auto i = 0; i < height; ++i ) {
        mvwprintz( w, at + point( 0, i ), color, "│" );
    }
}

auto width( const std::string &s ) -> int { return utf8_width( remove_color_tags( s ) ); }

}

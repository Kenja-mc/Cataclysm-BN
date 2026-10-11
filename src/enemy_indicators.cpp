#include "enemy_indicators.h"

#include <array>
#include <limits>
#if !defined( TILES ) && !defined( _WIN32 )
#include <langinfo.h>
#endif

#include "avatar.h"
#include "options.h"

namespace
{

/// Compass direction to a unit step, in the screen's x/y axes. Index 0 is north,
/// turning clockwise, like the compass in the sidebar.
constexpr auto octant_steps = std::array<point, 8> {{
        point( 0, -1 ), point( 1, -1 ), point( 1, 0 ), point( 1, 1 ),
        point( 0, 1 ), point( -1, 1 ), point( -1, 0 ), point( -1, -1 )
    }
};

/// Unicode arrows need a UTF-8 locale; plain ASCII terminals get the fallbacks.
auto unicode_arrows() -> bool
{
#if defined( TILES )
    return true;
#elif defined( _WIN32 )
    return true;
#else
    static const auto utf8 = std::strcmp( nl_langinfo( CODESET ), "UTF-8" ) == 0;
    return utf8;
#endif
}

auto arrow_glyphs() -> const std::array<std::string, 8> &
{
    if( unicode_arrows() ) {
        static const auto arrows = std::array<std::string, 8> {
            "\u2191", "\u2197", "\u2192", "\u2198", "\u2193", "\u2199", "\u2190", "\u2196"
        };
        return arrows;
    }
    static const auto arrows = std::array<std::string, 8> {
        "^", "/", ">", "\\", "v", "/", "<", "\\"
    };
    return arrows;
}

/// How many cells fit between the player and the window edge along one axis.
auto steps_to_edge( const int step, const int half, const int size ) -> int
{
    if( step == 0 ) {
        return std::numeric_limits<int>::max();
    }
    return step > 0 ? size - 1 - half : half;
}

} // namespace

namespace enemy_indicators
{

auto enabled() -> bool
{
    return get_option<bool>( "ENEMY_EDGE_ARROWS" );
}

auto map_arrows( const avatar &you, int width, int height ) -> std::vector<edge_arrow>
{
    if( !enabled() ) {
        return {};
    }
    const auto half = point( width / 2, height / 2 );
    const auto &glyphs = arrow_glyphs();
    const auto &offscreen = you.get_mon_visible().offscreen_hostiles;

    auto arrows = std::vector<edge_arrow>();
    for( int i = 0; i < 8; i++ ) {
        const auto &hostile = offscreen[i];
        if( hostile.count == 0 ) {
            continue;
        }
        const auto &step = octant_steps[i];
        const auto in_by_one = hostile.hunting ? 0 : 1;
        const auto cells = std::min( steps_to_edge( step.x, half.x, width ),
                                     steps_to_edge( step.y, half.y, height ) ) - in_by_one;
        arrows.push_back( {
            .offset = point( step.x * std::max( cells, 0 ), step.y * std::max( cells, 0 ) ),
            .glyph = glyphs[i],
            .color = hostile.threatening ? c_red : c_yellow
        } );
    }
    return arrows;
}

} // namespace enemy_indicators

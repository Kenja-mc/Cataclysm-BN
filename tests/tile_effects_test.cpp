#include "catch/catch.hpp"

#if defined(TILES)

#    include "tile_effects.h"
#    include "calendar.h"
#    include "effect.h"
#    include "monster.h"
#    include "type_id.h"

#    include <array>
#    include <climits>

TEST_CASE( "effect_overlay_frame_survives_negative_idle_counter", "[tiles][tile_effects]" )
{
    const auto ticks = std::array{
        INT_MIN, INT_MIN + 1, INT_MIN + 23, -2000000000, -1915784492, -25, -24, -23,
        -1, 0, 1, 23, 24, 2000000000, INT_MAX - 24, INT_MAX
    };
    for( const auto *effect : { "bleed", "poison", "cold", "onfire" } ) {
        auto critter = monster( mtype_id( "mon_zombie" ) );
        critter.add_effect( efftype_id( effect ), 1_hours );
        for( auto x = 0; x < 8; ++x ) {
            const auto options = tile_effects::overlay_options{
                .critter = critter, .pos = tripoint_bub_ms( x, 0, 0 )
            };
            for( const auto tick : ticks ) {
                CAPTURE( effect, tick, x );
                const auto canonical_tick = ( tick % 24 + 24 ) % 24;
                const auto *expected = tile_effects::overlay_tile_id( options, canonical_tick );
                REQUIRE( expected != nullptr );
                CHECK( tile_effects::overlay_tile_id( options, tick ) == expected );
            }
        }
    }
}

#endif // TILES

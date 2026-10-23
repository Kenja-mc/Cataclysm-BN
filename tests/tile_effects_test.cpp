#include "catch/catch.hpp"

#if defined(TILES)

#    include "tile_effects.h"

#    include "calendar.h"
#    include "effect.h"
#    include "monster.h"
#    include "type_id.h"

#    include <climits>
#    include <string>

// The idle animation counter was narrowed from a wall-clock epoch count into a signed
// int, which turned negative in late 2026. tile_effects::overlay_tile_id reduced that
// tick with plain %, so a negative counter indexed before the effect frame arrays and
// the tile renderer crashed hashing the resulting garbage string.
//
// Contract under test, on a real effect-bearing creature: for ANY idle tick the returned
// tile id must be the same one the equivalent in-loop tick returns. One full loop is
// 24 ticks (6 ticks per frame, 4 frames), so ticks 24 apart must draw the same frame.
// Walking the creature position staggers the phase, which exercises every negative
// subscript the broken remainder could produce (-3, -2, -1, 0 for a 4-frame loop).

namespace
{
struct effect_stage {
    const char *eff;
    const char *what;
};

} // namespace

TEST_CASE( "effect_overlay_frame_survives_negative_idle_counter", "[tiles][tile_effects]" )
{
    const effect_stage stages[] = {
        { "bleed", "bleed" },
        { "poison", "poison" },
        { "cold", "cold" },
        { "onfire", "onfire" },
    };

    for( const effect_stage &stage : stages ) {
        monster critter;
        critter.add_effect( efftype_id( stage.eff ), 1_hours );

        const int ticks[] = {
            INT_MIN, INT_MIN + 1, INT_MIN + 23, -2000000000, -1915784492, -25, -24, -23,
            -1, 0, 1, 23, 24, 2000000000, INT_MAX - 24, INT_MAX,
        };

        for( int x = 0; x < 8; ++x ) {
            // |31 * x| % 256 staggers the loop phase the way creature positions do.
            const tripoint_bub_ms pos( x, 0, 0 );
            const tile_effects::overlay_options opt{ critter, pos };

            for( int tick : ticks ) {
                CAPTURE( stage.what, tick, x );
                const std::string *frame = tile_effects::overlay_tile_id( opt, tick );
                REQUIRE( frame != nullptr );
                // Ticks one full loop apart must resolve to the same frame. Compared by
                // address so a broken index fails instead of dereferencing wild memory.
                CHECK( frame == tile_effects::overlay_tile_id( opt, tick + 24 ) );
            }
        }
    }
}

#endif // TILES

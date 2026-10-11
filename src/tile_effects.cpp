#if defined(TILES)

#include "tile_effects.h"

#include "cata_tiles.h"
#include "creature.h"
#include "effect.h"
#include "options.h"
#include "string_id.h"

#include <algorithm>
#include <array>
#include <cstdlib>
#include <ranges>
#include <string>
#include <utility>

namespace
{

const std::string empty_string;

/// The frames of one looping state, in the order they are played.
struct status_stage {
    const std::string *frames;
    int frame_count;
};

const std::string bleed_frames[] = {
    "overlay_fx_bleed_0", "overlay_fx_bleed_1", "overlay_fx_bleed_2", "overlay_fx_bleed_3",
};
const std::string toxic_frames[] = {
    "overlay_fx_toxic_0", "overlay_fx_toxic_1", "overlay_fx_toxic_2", "overlay_fx_toxic_3",
};
const std::string dizzy_frames[] = {
    "overlay_fx_dizzy_0", "overlay_fx_dizzy_1", "overlay_fx_dizzy_2", "overlay_fx_dizzy_3",
};
const std::string sleep_frames[] = {
    "overlay_fx_sleep_0", "overlay_fx_sleep_1", "overlay_fx_sleep_2", "overlay_fx_sleep_3",
};
const std::string cold_frames[] = {
    "overlay_fx_cold_0", "overlay_fx_cold_1", "overlay_fx_cold_2", "overlay_fx_cold_3",
};
/// Already a six frame loop in the shipped tileset, so it needs no copy of its own.
const std::string burn_frames[] = { "overlay_effect_onfire" };

const std::array<status_stage, 6> stages = {{
    { burn_frames, 1 },
    { bleed_frames, 4 },
    { toxic_frames, 4 },
    { dizzy_frames, 4 },
    { sleep_frames, 4 },
    { cold_frames, 4 },
}};

/// An effect that makes a creature show one of the states above.
struct status_binding {
    efftype_id effect;
    const status_stage *stage;
};

/// In drawing priority: a creature on fire shows that above anything else.
const std::array<status_binding, 13> bindings = {{
    { efftype_id( "onfire" ), &stages[0] },
    { efftype_id( "bleed" ), &stages[1] },
    { efftype_id( "poison" ), &stages[2] },
    { efftype_id( "badpoison" ), &stages[2] },
    { efftype_id( "paralyzepoison" ), &stages[2] },
    { efftype_id( "foodpoison" ), &stages[2] },
    { efftype_id( "nausea" ), &stages[2] },
    { efftype_id( "stunned" ), &stages[3] },
    { efftype_id( "dazed" ), &stages[3] },
    { efftype_id( "sleep" ), &stages[4] },
    { efftype_id( "cold" ), &stages[5] },
    { efftype_id( "frostbite" ), &stages[5] },
}};

/// The idle animation manager ticks roughly 60 times a second; the overlays change
/// frame once every six ticks so a full loop lasts a little under a second.
constexpr int idle_frames_per_loop_frame = 6;

auto has_active_effect( const effects_map &effects, const efftype_id &eff ) -> bool
{
    const auto it = effects.find( eff );
    return it != effects.end() && std::ranges::any_of( it->second, []( const auto &entry ) {
        return !entry.second.is_removed();
    } );
}

auto stage_for( const Creature &critter ) -> const status_stage *
{
    const effects_map &effects = critter.get_effects();
    for( const status_binding &binding : bindings ) {
        if( has_active_effect( effects, binding.effect ) ) {
            return binding.stage;
        }
    }
    return nullptr;
}

auto phase_of( const tripoint_bub_ms &pos ) -> int
{
    return std::abs( pos.x() * 31 + pos.y() * 17 + pos.z() * 7 ) % 256;
}

} // namespace

namespace tile_effects
{

auto enabled() -> bool
{
    return ::get_option<bool>( "TILE_EFFECT_ANIMATIONS" );
}

auto overlay_tile_id( const overlay_options &opt, int idle_frame ) -> const std::string *
{
    const status_stage *stage = stage_for( opt.critter );
    if( stage == nullptr ) {
        return nullptr;
    }
    const int frame = ( idle_frame / idle_frames_per_loop_frame + phase_of( opt.pos ) ) %
                      stage->frame_count;
    return &stage->frames[frame];
}

auto owns_effect( std::string_view effect_id ) -> bool
{
    return std::ranges::any_of( bindings, [&]( const status_binding & binding ) {
        return binding.effect.str() == effect_id;
    } );
}

} // namespace tile_effects

void cata_tiles::draw_status_effects( const Creature &critter, const tripoint_bub_ms &p,
                                      lit_level ll, int z_drop )
{
    if( !tile_effects::enabled() ) {
        return;
    }
    const tile_effects::overlay_options opt{ .critter = critter, .pos = p };
    const std::string *overlay_id = tile_effects::overlay_tile_id( opt,
                                     idle_animations.current_frame() );
    if( overlay_id == nullptr ) {
        return;
    }
    const tile_search_params tile{ *overlay_id, C_NONE, empty_string, 0, 0 };
    draw_from_id_string( tile, p, std::nullopt, std::nullopt, ll, false, z_drop, false );
    // Keeps the map redrawing while the loop plays, the way animated terrain tiles do.
    idle_animations.mark_present();
}

#endif // TILES

#include "map_overlay.h"

#include <vector>

#include "aim_reticle.h"
#include "avatar.h"
#include "coordinates.h"
#include "game.h"
#include "map/map.h"
#include "map_memory.h"
#include "monster.h"
#include "options.h"
#include "shot_preview.h"
#include "sounds.h"
#include "tile_selection.h"
#include "type_id.h"

namespace
{

const trait_id trait_INATTENTIVE( "INATTENTIVE" );

auto sound_flavor_of( const sounds::sound_t category ) -> map_overlay::sound_flavor
{
    using sounds::sound_t;
    switch( category ) {
        case sound_t::combat:
        case sound_t::alarm:
        case sound_t::destructive_activity:
            return map_overlay::sound_flavor::violent;
        case sound_t::speech:
        case sound_t::electronic_speech:
        case sound_t::alert:
        case sound_t::order:
            return map_overlay::sound_flavor::talk;
        default:
            return map_overlay::sound_flavor::plain;
    }
}

auto add_sound_markers( std::vector<map_overlay::overlay> &out, const avatar &you ) -> void
{
    const auto center = you.bub_pos() + you.view_offset;
    const auto age_glyphs = get_option<bool>( "SOUND_MARKER_GLYPH_AGING" );
    for( const auto &mark : sounds::get_footstep_markers() ) {
        out.push_back( map_overlay::overlay{
            .pos = mark.pos,
            .kind = map_overlay::overlay_kind::sound_marker,
            .age = mark.age,
            .z_offset = mark.pos.z() - center.z(),
            .stale = mark.age >= 2 && age_glyphs,
            .flavor = sound_flavor_of( mark.category ),
        } );
    }
}

auto add_reticle( std::vector<map_overlay::overlay> &out, const avatar &you ) -> void
{
    const auto reticle = aim_reticle::pos();
    if( !reticle || you.view_offset.z() != 0 || tile_selection::hovered() == reticle ) {
        return;
    }
    out.push_back( map_overlay::overlay{
        .pos = *reticle,
        .kind = map_overlay::overlay_kind::reticle,
    } );
}

auto add_known_locks( std::vector<map_overlay::overlay> &out, const avatar &you ) -> void
{
    for( const auto &abs : you.known_locked_door_positions() ) {
        const auto kind = you.get_known_locked_door( abs );
        if( kind == locked_door_kind::none ) {
            continue;
        }
        out.push_back( map_overlay::overlay{
            .pos = abs_to_bub( abs ),
            .kind = map_overlay::overlay_kind::known_lock,
            .severity = static_cast<int>( kind ),
        } );
    }
}

auto add_health_bars( std::vector<map_overlay::overlay> &out, const avatar &you ) -> void
{
    if( g == nullptr || !get_option<bool>( "MONSTER_HEALTH_BARS" ) ||
        you.has_trait( trait_INATTENTIVE ) ) {
        return;
    }
    for( const monster &mon : g->all_monsters() ) {
        const auto hp = mon.get_hp();
        const auto max_hp = mon.get_hp_max();
        if( hp <= 0 || hp >= max_hp || !you.sees( mon ) ) {
            continue;
        }
        out.push_back( map_overlay::overlay{
            .pos = mon.bub_pos(),
            .kind = map_overlay::overlay_kind::health_bar,
            .severity = max_hp > 0 ? hp * 100 / max_hp : 0,
            .value = hp,
            .max_value = max_hp,
        } );
    }
}

auto add_shot_preview( std::vector<map_overlay::overlay> &out ) -> void
{
    const auto &preview = shot_preview::current();
    if( !preview.active ) {
        return;
    }
    if( preview.blocker ) {
        out.push_back( map_overlay::overlay{
            .pos = preview.blocker->pos,
            .kind = map_overlay::overlay_kind::shot_blocker,
            .severity = preview.blocker->severity,
            .label = preview.blocker->label,
        } );
    }
    for( const tripoint_bub_ms &p : preview.strays ) {
        out.push_back( map_overlay::overlay{
            .pos = p,
            .kind = map_overlay::overlay_kind::stray_tile,
        } );
    }
    if( preview.aim_label ) {
        out.push_back( map_overlay::overlay{
            .pos = preview.aim_label->pos,
            .kind = map_overlay::overlay_kind::aim_label,
            .severity = preview.aim_label->severity,
            .label = preview.aim_label->label,
        } );
    }
}

} // namespace

namespace map_overlay
{

auto collect( const avatar &you ) -> std::vector<overlay>
{
    std::vector<overlay> out;
    add_sound_markers( out, you );
    add_reticle( out, you );
    add_known_locks( out, you );
    add_health_bars( out, you );
    add_shot_preview( out );
    return out;
}

auto kind_name( const overlay_kind kind ) -> std::string
{
    switch( kind ) {
        case overlay_kind::sound_marker:
            return "sound_marker";
        case overlay_kind::reticle:
            return "reticle";
        case overlay_kind::known_lock:
            return "known_lock";
        case overlay_kind::health_bar:
            return "health_bar";
        case overlay_kind::shot_blocker:
            return "shot_blocker";
        case overlay_kind::stray_tile:
            return "stray_tile";
        case overlay_kind::aim_label:
            return "aim_label";
    }
    return "unknown";
}

} // namespace map_overlay

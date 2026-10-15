#include "aim_reticle.h"

#include <algorithm>
#include <array>
#include <ranges>

#include "avatar.h"
#include "avatar_action.h"
#include "creature.h"
#include "game.h"
#include "input.h"
#include "map/map.h"
#include "messages.h"
#include "monster.h"
#include "npc.h"
#include "options.h"
#include "tile_selection.h"
#include "translations.h"

namespace
{

auto reticle = std::optional<tripoint_bub_ms>();

auto hostile_at( const avatar &you, const tripoint_bub_ms &p ) -> Creature * // *NOPAD*
{
    auto *critter = g->critter_at<Creature>( p, true );
    if( critter == nullptr || critter == &you || !you.sees( *critter ) ) {
        return nullptr;
    }
    if( const auto *guy = dynamic_cast<const npc *>( critter ) ) {
        return guy->is_enemy() ? critter : nullptr;
    }
    return critter->attitude_to( you ) == Attitude::A_HOSTILE ? critter : nullptr;
}

auto start_pos( const avatar &you ) -> tripoint_bub_ms
{
    const auto hostiles = you.get_hostile_creatures( g_max_view_distance );
    const auto nearest = std::ranges::min_element( hostiles, {}, [&]( const Creature * cr ) {
        return rl_dist( cr->bub_pos(), you.bub_pos() );
    } );
    return nearest != hostiles.end() ? ( *nearest )->bub_pos() : you.bub_pos();
}

auto weapon_reaches( const avatar &you, const Creature &target ) -> bool
{
    const auto &weapon = you.primary_weapon();
    const auto dist = rl_dist( target.bub_pos(), you.bub_pos() );
    if( weapon.is_gun() && !weapon.gun_current_mode().melee() ) {
        return dist <= weapon.gun_range();
    }
    return dist <= std::max( 1, weapon.reach_range( you ) );
}

} // namespace

namespace aim_reticle
{

auto enabled() -> bool
{
    return get_option<bool>( "ARROW_KEY_AIM" );
}

auto active() -> bool
{
    return enabled() && reticle.has_value();
}

auto pos() -> std::optional<tripoint_bub_ms>
{
    return active() ? reticle : std::nullopt;
}

auto arrow_move( const action_id act, input_context &ctxt ) -> bool
{
    if( act < ACTION_MOVE_FORTH || act > ACTION_MOVE_FORTH_LEFT ) {
        return false;
    }
    const auto &evt = ctxt.get_raw_input();
    if( evt.type != input_event_t::keyboard ) {
        return false;
    }
    constexpr auto arrows = std::array{ KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT };
    return std::ranges::contains( arrows, evt.get_first_input() );
}

auto move( avatar &you, map &m, const point_rel_ms &delta ) -> void
{
    if( !enabled() ) {
        clear();
        return;
    }
    if( !reticle || reticle->z() != you.bub_pos().z() ) {
        reticle = start_pos( you );
    } else {
        const auto next = tripoint_bub_ms( reticle->xy() + delta, reticle->z() );
        if( m.inbounds( next ) && you.sees( next ) ) {
            reticle = next;
        }
    }
    tile_selection::hover( you, m, reticle );
}

auto attack( avatar &you, map &m ) -> std::optional<action_id>
{
    if( !enabled() ) {
        clear();
        return std::nullopt;
    }
    if( !reticle ) {
        return std::nullopt;
    }
    const auto p = *reticle;
    auto *target = hostile_at( you, p );
    if( target == nullptr ) {
        add_msg( m_info, _( "There's nothing there to attack." ) );
        return ACTION_NULL;
    }

    const auto diff = p - you.bub_pos();
    const auto adjacent = std::abs( diff.x() ) <= 1 && std::abs( diff.y() ) <= 1 && diff.z() == 0;
    const auto melee = !you.primary_weapon().is_gun();
    if( adjacent && melee ) {
        clear();
        avatar_action::attack_at( you, m, tripoint_rel_ms( diff.xy(), 0 ) );
        return ACTION_NULL;
    }

    if( !weapon_reaches( you, *target ) ) {
        add_msg( m_info, _( "%s is out of your weapon's reach." ), target->disp_name() );
        return ACTION_NULL;
    }

    // Aim at the creature the reticle covers, not whichever hostile is nearest.
    you.last_target = g->shared_from( *target );
    clear();
    return ACTION_FIRE;
}

auto clear() -> bool
{
    if( !reticle ) {
        return false;
    }
    const auto was = reticle;
    reticle.reset();
    if( tile_selection::hovered() == was ) {
        tile_selection::clear_hover();
    }
    return true;
}

} // namespace aim_reticle
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

auto is_hostile( const avatar &you, const Creature &critter ) -> bool
{
    if( &critter == &you || critter.is_dead_state() || !you.sees( critter ) ) {
        return false;
    }
    if( const auto *guy = dynamic_cast<const npc *>( &critter ) ) {
        return guy->is_enemy();
    }
    return critter.attitude_to( you ) == Attitude::A_HOSTILE;
}

auto hostile_at( const avatar &you, const tripoint_bub_ms &p ) -> Creature * // *NOPAD*
{
    auto *critter = g->critter_at<Creature>( p, true );
    return critter != nullptr && is_hostile( you, *critter ) ? critter : nullptr;
}

struct target_rank {
    int distance;
    tripoint_bub_ms pos;
};

auto rank_less( const target_rank &lhs, const target_rank &rhs ) -> bool
{
    return lhs.distance != rhs.distance ? lhs.distance < rhs.distance : lhs.pos < rhs.pos;
}

auto next_target( const avatar &you, const std::optional<tripoint_bub_ms> &after,
                  const bool reverse ) -> std::optional<tripoint_bub_ms>
{
    const auto &m = get_map();
    const auto current = after ? std::optional<target_rank>(
                             target_rank{ .distance = rl_dist( you.bub_pos(), *after ), .pos = *after } ) : std::nullopt;
    auto first = std::optional<target_rank>();
    auto next = std::optional<target_rank>();
    auto current_found = false;
    const auto before = [reverse]( const auto & lhs, const auto & rhs ) { return reverse ? rank_less( rhs, lhs ) : rank_less( lhs, rhs ); };
    for( const auto &critter : g->all_creatures() ) {
        const auto p = critter.bub_pos();
        if( p.z() != you.bub_pos().z() || !m.inbounds( p ) ) {
            continue;
        }
        const auto distance = rl_dist( you.bub_pos(), p );
        if( distance > g_max_view_distance || !is_hostile( you, critter ) || !you.sees( p ) ) {
            continue;
        }
        const auto rank = target_rank{ .distance = distance, .pos = p };
        current_found = current_found || ( after && p == *after );
        if( !first || before( rank, *first ) ) {
            first = rank;
        }
        if( current && before( *current, rank ) && ( !next || before( rank, *next ) ) ) {
            next = rank;
        }
    }
    if( current_found && next ) {
        return next->pos;
    }
    return first ? std::optional<tripoint_bub_ms>( first->pos ) : std::nullopt;
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
    return reticle.has_value();
}

auto pos() -> std::optional<tripoint_bub_ms>
{
    return active() ? reticle : std::nullopt;
}

auto select( avatar &you, map &m, const tripoint_bub_ms &p ) -> bool
{
    if( p.z() != you.bub_pos().z() || !m.inbounds( p ) || !you.sees( p ) ) {
        return false;
    }
    reticle = p;
    tile_selection::hover( you, m, reticle );
    return true;
}

auto cycle( avatar &you, map &m, const bool reverse ) -> bool
{
    const auto target = next_target( you, reticle, reverse );
    if( !target ) {
        clear();
        add_msg( _( "There are no visible hostile targets." ) );
        return false;
    }
    reticle = target;
    tile_selection::hover( you, m, reticle );
    return true;
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

auto attack( avatar &you, map &m, const attack_mode mode ) -> std::optional<action_id>
{
    if( !reticle ) {
        return std::nullopt;
    }
    const auto p = *reticle;
    auto *target = hostile_at( you, p );
    if( target == nullptr ) {
        const auto &weapon = you.primary_weapon();
        if( mode == attack_mode::fire_command && weapon.is_gun() &&
            !weapon.gun_current_mode().melee() ) {
            clear();
            return ACTION_FIRE;
        }
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
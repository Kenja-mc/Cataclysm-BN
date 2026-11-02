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
#include "output.h"
#include "tile_selection.h"
#include "translations.h"
#include "type_id.h"
#include "ui.h"

namespace
{

static const enchantment_value_id ench_val_REACH_RANGE_UNARMED( "REACH_RANGE_UNARMED" );

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

auto melee_reach( const avatar &you ) -> int
{
    if( you.is_armed() ) {
        return std::max( 1, you.primary_weapon().reach_range( you ) );
    }
    const auto reach = 1.0 + you.bonus_from_enchantments( 0, ench_val_REACH_RANGE_UNARMED, true );
    return std::max( 1, static_cast<int>( reach ) );
}

/// A firearm aimed in a firing mode. A gun left in melee mode counts as a melee weapon.
auto is_firearm( const avatar &you ) -> bool
{
    const auto &weapon = you.primary_weapon();
    return weapon.is_gun() && !weapon.gun_current_mode().melee();
}

/// A firearm that can fire at least one shot in its current mode.
auto is_loaded_gun( const avatar &you ) -> bool
{
    return is_firearm( you ) && you.primary_weapon().ammo_sufficient();
}

auto weapon_reaches( const avatar &you, const Creature &target, const bool melee_only )
{
    const auto &weapon = you.primary_weapon();
    const auto dist = rl_dist( target.bub_pos(), you.bub_pos() );
    if( !melee_only && weapon.is_gun() && !weapon.gun_current_mode().melee() ) {
        return dist <= weapon.gun_range();
    }
    return dist <= melee_reach( you );
}

/// The nearest visible hostile within melee reach. A plain attack with a firearm in a firing
/// mode only clears an adjacent enemy, so the aiming screen still opens for a nearby shot;
/// Shift+F may use an attached bayonet's reach.
auto nearest_hostile_in_reach( const avatar &you, const bool force_melee )
    -> std::optional<tripoint_bub_ms>
{
    // A firearm in a firing mode clears only the tile it could bash on a plain attack; a
    // bayonet is used deliberately with Shift+F. A melee weapon uses its full reach.
    const auto reach = force_melee || !is_firearm( you ) ? melee_reach( you ) : 1;
    auto best = std::optional<target_rank>();
    for( const auto &critter : g->all_creatures() ) {
        const auto p = critter.bub_pos();
        if( p.z() != you.bub_pos().z() || !is_hostile( you, critter ) || !you.sees( p ) ) {
            continue;
        }
        const auto distance = rl_dist( you.bub_pos(), p );
        if( distance > reach ) {
            continue;
        }
        const auto rank = target_rank{ .distance = distance, .pos = p };
        if( !best || rank_less( rank, *best ) ) {
            best = rank;
        }
    }
    return best ? std::optional<tripoint_bub_ms>( best->pos ) : std::nullopt;
}

/// Attack a hostile the weapon reaches in place: a bump when adjacent, a reach swing when not.
auto attack_reachable( avatar &you, map &m, const tripoint_bub_ms &p ) -> void
{
    const auto diff = p - you.bub_pos();
    if( std::abs( diff.x() ) <= 1 && std::abs( diff.y() ) <= 1 && diff.z() == 0 ) {
        avatar_action::attack_at( you, m, tripoint_rel_ms( diff.xy(), 0 ) );
    } else {
        you.reach_attack( p );
    }
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

auto attack( avatar &you, map &m, const attack_options &opts ) -> std::optional<action_id>
{
    const auto mode = opts.mode;
    const auto force_melee = opts.force_melee;
    if( !reticle ) {
        if( mode == attack_mode::direct ) {
            return std::nullopt;
        }
        // With nothing selected, attack what the weapon reaches in melee, in place. This
        // comes before the aiming screen, so an adjacent enemy is a swing, not a shot.
        if( nearest_hostile_in_reach( you, force_melee ) ) {
            avatar_action::autoattack( you, m );
            return ACTION_NULL;
        }
        if( force_melee ) {
            add_msg( m_info, _( "No hostile creature is within your weapon's reach." ) );
            return ACTION_NULL;
        }
        // A loaded gun, and only a loaded gun, opens the ordinary aiming screen. It comes
        // before smashing so the key keeps its ranged meaning while the weapon can shoot.
        if( is_loaded_gun( you ) ) {
            return ACTION_FIRE;
        }
        // Otherwise break what the last step faced. Only a real object, field or reviving
        // corpse counts, so walking on open floor never turns the attack key into digging.
        if( const auto faced = tile_selection::facing_tile( you );
            faced && tile_selection::reachable( you, *faced ) &&
            tile_selection::smashable_at( you, *faced ) ) {
            tile_selection::smash_at( *faced );
            return ACTION_NULL;
        }
        if( is_firearm( you ) ) {
            add_msg( m_info, _( "Your %s is not loaded." ), you.primary_weapon().tname() );
            return ACTION_NULL;
        }
        return std::nullopt;
    }

    const auto p = *reticle;
    auto *target = hostile_at( you, p );
    if( target != nullptr ) {
        // A melee weapon, a gun left in a melee mode, and a forced melee all swing at the
        // aimed creature in one step. Only a firearm in a firing mode opens the aiming screen.
        if( force_melee || !is_firearm( you ) ) {
            if( !weapon_reaches( you, *target, true ) ) {
                add_msg( m_info, _( "%s is out of your weapon's reach." ), target->disp_name() );
                return ACTION_NULL;
            }
            clear();
            attack_reachable( you, m, p );
            return ACTION_NULL;
        }

        if( !weapon_reaches( you, *target, false ) ) {
            add_msg( m_info, _( "%s is out of your weapon's reach." ), target->disp_name() );
            return ACTION_NULL;
        }

        // Aim at the creature the reticle covers, not whichever hostile is nearest.
        you.last_target = g->shared_from( *target );
        clear();
        return ACTION_FIRE;
    }

    // A direct click only ever attacks the creature under it. Smashing and pulping belong to
    // the fire command, so a click on terrain keeps its old meaning.
    if( mode == attack_mode::direct || force_melee ) {
        add_msg( m_info, _( "There's nothing there to attack." ) );
        return ACTION_NULL;
    }

    const auto reachable = tile_selection::reachable( you, p );
    const auto smashable = tile_selection::smashable_at( you, p );
    const auto corpse = tile_selection::corpse_at( p );
    const auto firearm = is_firearm( you );
    const auto loaded = is_loaded_gun( you );

    if( corpse && loaded ) {
        auto menu = uilist();
        menu.title = _( "Attack the selected tile" );
        menu.addentry( 0, true, 'f', _( "Fire" ) );
        if( reachable && smashable ) {
            menu.addentry( 1, true, 'p', _( "Pulp" ) );
        }
        menu.query();
        if( menu.ret == 0 ) {
            return ACTION_FIRE;
        }
        if( menu.ret == 1 && reachable && smashable ) {
            clear();
            tile_selection::smash_at( p );
        }
        return ACTION_NULL;
    }

    if( reachable && smashable ) {
        clear();
        tile_selection::smash_at( p );
        return ACTION_NULL;
    }
    if( loaded ) {
        // The firing UI consumes this selection as its initial cursor position.
        return ACTION_FIRE;
    }
    if( !reachable && ( smashable || corpse ) ) {
        add_msg( m_info, _( "That is out of your reach." ) );
        return ACTION_NULL;
    }
    if( firearm ) {
        add_msg( m_info, _( "Your %s is not loaded." ), you.primary_weapon().tname() );
        return ACTION_NULL;
    }
    add_msg( m_info, _( "There's nothing there to attack." ) );
    return ACTION_NULL;
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
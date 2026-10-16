#include "tile_selection.h"

#include <optional>

#include "action.h"
#include "avatar.h"
#include "creature.h"
#include "game.h"
#include "input.h"
#include "item.h"
#include "map/map.h"
#include "messages.h"
#include "monster.h"
#include "npc.h"
#include "options.h"
#include "player_activity.h"
#include "smart_safemode.h"
#include "string_formatter.h"
#include "translations.h"
#include "trap.h"
#include "travel/travel_destination.h"

namespace
{

auto hovered_tile = std::optional<tripoint_bub_ms>();
auto hovered_route = std::vector<tripoint_bub_ms>();
/// Turn the hover was computed on; a new turn can change what a click does.
auto hovered_turn = std::optional<time_point>();
auto hovered_mouse_move = false;
auto hovered_hint = std::string();
auto pending_click = std::optional<tripoint_bub_ms>();

auto hostile_in_view( avatar &you ) -> bool
{
    const auto hostiles = you.get_hostile_creatures( g_max_view_distance );
    const auto as_monster = []( const Creature * cr ) { return dynamic_cast<const monster *>( cr ); };
    if( std::ranges::any_of( hostiles, [&]( const Creature * cr ) { return as_monster( cr ) == nullptr; } ) ) {
        return true;
    }
    auto monsters = hostiles
                    | std::views::transform( as_monster )
                    | std::ranges::to<std::vector<const monster *>>();
    return smart_safemode::any_threatens( monsters, you );
}

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

auto route_to( avatar &you, map &m, const tripoint_bub_ms &p ) -> std::vector<tripoint_bub_ms>
{
    return m.route( you.bub_pos(), p, you.get_legacy_pathfinding_settings(), you.get_legacy_path_avoid() );
}

auto confirm_hint( const size_t n ) -> std::string
{
    return string_format( vgettext( "click again to walk here (%d step)",
                                    "click again to walk here (%d steps)", n ), n );
}

auto dangerous_dest( map &m, const avatar &you, const tripoint_bub_ms &p ) -> bool
{
    if( m.dangerous_field_at( p ) ) {
        return true;
    }
    const auto &tr = m.tr_at( p );
    return !tr.is_null() && !tr.is_benign() && ( you.knows_trap( p ) || tr.can_see( p, you ) );
}

auto bound_key_suffix( const action_id act ) -> std::string
{
    static auto cache = std::vector<std::optional<std::string>>();
    static auto cache_version = -1;
    static auto cache_lang = -1;
    const auto version = inp_mngr.bindings_version();
    const auto lang = detail::get_current_language_version();
    if( cache_version != version || cache_lang != lang ) {
        cache.assign( NUM_ACTIONS, std::nullopt );
        cache_version = version;
        cache_lang = lang;
    }
    if( act == ACTION_NULL || static_cast<int>( act ) >= NUM_ACTIONS ) {
        return std::string();
    }
    const auto idx = static_cast<size_t>( act );
    if( !cache[idx] ) {
        cache[idx] = press_x( act, " [", "]", "" );
    }
    return cache[idx].value_or( std::string() );
}

} // namespace

namespace tile_selection
{

auto enabled() -> bool { return get_option<bool>( "MOUSE_TILE_SELECTION" ); }

auto choices_at( const avatar &you, const tripoint_bub_ms &p ) -> std::vector<choice>
{
    auto &m = get_map();
    auto out = std::vector<choice>();
    if( p.z() != you.bub_pos().z() ) {
        return out;
    }
    const auto dist = square_dist( p.xy(), you.bub_pos().xy() );
    const auto adjacent = dist == 1;
    const auto *target = hostile_at( you, p );
    if( target != nullptr && adjacent ) {
        out.push_back( { .act = ACTION_ATTACK, .label = string_format( _( "attack %s" ), target->disp_name() ) } );
    }
    if( target != nullptr && you.primary_weapon().is_gun() ) {
        out.push_back( { .act = ACTION_FIRE, .label = string_format( _( "fire at %s" ), target->disp_name() ) } );
    }
    if( adjacent && m.can_open_door( &you, p, !m.is_outside( you.bub_pos() ) ) ) {
        out.push_back( { .act = ACTION_OPEN, .label = string_format( _( "open the %s" ), m.name( p ) ) } );
    }
    if( adjacent && m.close_door( p, !m.is_outside( you.bub_pos() ), true ) ) {
        out.push_back( { .act = ACTION_CLOSE, .label = string_format( _( "close the %s" ), m.name( p ) ) } );
    }
    if( dist <= 1 && m.has_items( p ) && m.sees_some_items( p, you ) ) {
        out.push_back( { .act = ACTION_PICKUP, .label = _( "pick up items" ) } );
    }
    if( adjacent && target == nullptr && can_examine_at( p ) ) {
        out.push_back( { .act = ACTION_EXAMINE, .label = string_format( _( "examine the %s" ), m.name( p ) ) } );
    }
    if( get_option<bool>( "MOUSE_MOVE" ) && dist > 0 && target == nullptr &&
        avatar_knows_travel_destination( you, p ) && m.passable( p ) ) {
        out.push_back( { .label = adjacent ? _( "step here" ) : _( "walk here" ), .travel = true } );
    }
    return out;
}


auto resolve( avatar &you, map &m, const choice &c, const tripoint_bub_ms &p ) -> action_id
{
    if( !c.travel ) {
        pending_click.reset();
    }

    if( c.act == ACTION_OPEN ) {
        // Walking into a closed door opens it.
        return get_movement_action_from_delta( p - you.bub_pos(), iso_rotate::yes );
    }
    if( c.act == ACTION_FIRE ) {
        // Aim at the creature the hint named, not whichever hostile is nearest.
        if( auto *target = hostile_at( you, p ) ) {
            you.last_target = g->shared_from( *target );
        }
        return c.act;
    }
    if( !c.travel ) {
        return c.act;
    }
    if( !get_option<bool>( "MOUSE_MOVE" ) ) {
        pending_click.reset();
        return ACTION_NULL;
    }
    const auto dist = square_dist( p.xy(), you.bub_pos().xy() );
    const auto safe = get_option<bool>( "SAFE_CLICK_WALK" );
    const auto dangerous = dangerous_dest( m, you, p );
    const auto hostiles = safe && dist > 1 ? hostile_in_view( you ) : false;
    const auto route = route_to( you, m, p );
    if( route.empty() ) {
        add_msg( m_info, _( "You can't find a way there." ) );
        return ACTION_NULL;
    }
    if( safe && ( dist > 1 || dangerous ) && pending_click != p &&
        ( dangerous || !hostiles ) ) {
        pending_click = p;
        hovered_route = route;
        hovered_hint = dangerous ? std::string( _( "click again: walk into danger" ) ) :
                       confirm_hint( route.size() );
        return ACTION_NULL;
    }
    pending_click.reset();
    you.set_destination( route );
    const auto step = you.get_next_auto_move_direction();
    if( hostiles || step == ACTION_NULL ) {
        you.clear_destination();
    }
    return step;
}

auto hover( avatar &you, map &m, const std::optional<tripoint_bub_ms> &p ) -> void
{
    const auto mouse_move = get_option<bool>( "MOUSE_MOVE" );
    if( !mouse_move || !get_option<bool>( "SAFE_CLICK_WALK" ) ) {
        pending_click.reset();
    }
    if( !p || !enabled() || !m.inbounds( *p ) || p->z() != you.bub_pos().z() ||
        ( !mouse_move && !you.sees( *p ) ) ) {
        clear_hover();
        return;
    }
    if( hovered_tile != p ) {
        pending_click.reset();
    }
    if( hovered_tile == p && hovered_turn == calendar::turn && hovered_mouse_move == mouse_move ) {
        return;
    }
    hovered_tile = p;
    hovered_turn = calendar::turn;
    hovered_mouse_move = mouse_move;
    if( !mouse_move ) {
        hovered_route.clear();
        pending_click.reset();
        hovered_hint = _( "left: attack; right: select" );
        return;
    }
    const auto choices = choices_at( you, *p );
    const auto dist = square_dist( p->xy(), you.bub_pos().xy() );
    hovered_route = !choices.empty() && choices.front().travel &&
                    dist > 1 ? route_to( you, m, *p ) : std::vector<tripoint_bub_ms>();
    const auto safe = get_option<bool>( "SAFE_CLICK_WALK" );
    if( choices.empty() ) {
        hovered_hint.clear();
    } else if( choices.front().travel && safe && dangerous_dest( m, you, *p ) ) {
        hovered_hint = pending_click == p ? _( "click again: walk into danger" ) :
                       _( "click: confirm walking into danger" );
    } else if( choices.front().travel && !hovered_route.empty() ) {
        auto base = string_format( vgettext( "click: walk here (%d step)", "click: walk here (%d steps)",
                                             hovered_route.size() ), hovered_route.size() );
        if( safe && pending_click == p ) {
            hovered_hint = confirm_hint( hovered_route.size() );
        } else if( safe && dist > 1 && hostile_in_view( you ) ) {
            hovered_hint = _( "click: step toward (hostile in view)" );
        } else {
            hovered_hint = base;
        }
    } else {
        // Name the key too, so the mouse teaches the keyboard.
        const auto act = choices.front().act;
        const auto key = act == ACTION_NULL ? std::string() : bound_key_suffix( act );
        hovered_hint = string_format( _( "click: %s" ), choices.front().label ) + key;
    }
    if( choices.size() > 1 ) {
        hovered_hint += _( "  right-click: more" );
    }
}

auto clear_hover() -> void
{
    hovered_tile.reset();
    hovered_route.clear();
    hovered_hint.clear();
    pending_click.reset();
}

auto hovered() -> std::optional<tripoint_bub_ms> { return hovered_tile; }

auto hover_path() -> const std::vector<tripoint_bub_ms> & { return hovered_route; } // *NOPAD*

auto hint() -> std::string { return hovered_hint; }

} // namespace tile_selection

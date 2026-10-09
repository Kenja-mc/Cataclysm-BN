#include "tile_selection.h"

#include "action.h"
#include "avatar.h"
#include "creature.h"
#include "game.h"
#include "item.h"
#include "map/map.h"
#include "messages.h"
#include "npc.h"
#include "options.h"
#include "player_activity.h"
#include "string_formatter.h"
#include "translations.h"
#include "travel/travel_destination.h"

namespace
{

auto hovered_tile = std::optional<tripoint_bub_ms>();
auto hovered_route = std::vector<tripoint_bub_ms>();
auto hovered_hint = std::string();

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
    if( dist > 0 && target == nullptr && avatar_knows_travel_destination( you, p ) && m.passable( p ) ) {
        out.push_back( { .label = adjacent ? _( "step here" ) : _( "walk here" ), .travel = true } );
    }
    return out;
}

auto resolve( avatar &you, map &m, const choice &c, const tripoint_bub_ms &p ) -> action_id
{
    if( c.act == ACTION_OPEN ) {
        // Walking into a closed door opens it.
        return get_movement_action_from_delta( p - you.bub_pos(), iso_rotate::yes );
    }
    if( !c.travel ) {
        return c.act;
    }
    const auto route = route_to( you, m, p );
    if( route.empty() ) {
        add_msg( m_info, _( "You can't find a way there." ) );
        return ACTION_NULL;
    }
    you.set_destination( route );
    const auto step = you.get_next_auto_move_direction();
    if( step == ACTION_NULL ) {
        you.clear_destination();
    }
    return step;
}

auto hover( avatar &you, map &m, const std::optional<tripoint_bub_ms> &p ) -> void
{
    if( !p || !enabled() ) {
        clear_hover();
        return;
    }
    if( hovered_tile == p ) {
        return;
    }
    hovered_tile = p;
    const auto choices = choices_at( you, *p );
    hovered_route = !choices.empty() && choices.front().travel &&
                    square_dist( p->xy(), you.bub_pos().xy() ) > 1 ? route_to( you, m, *p ) : std::vector<tripoint_bub_ms>();
    if( choices.empty() ) {
        hovered_hint.clear();
    } else if( choices.front().travel && !hovered_route.empty() ) {
        hovered_hint = string_format( vgettext( "click: walk here (%d step)", "click: walk here (%d steps)",
                                       hovered_route.size() ), hovered_route.size() );
    } else {
        // Name the key too, so the mouse teaches the keyboard.
        const auto act = choices.front().act;
        const auto key = act == ACTION_NULL ? std::string() : press_x( act, " [", "]", "" );
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
}

auto hovered() -> std::optional<tripoint_bub_ms> { return hovered_tile; }

auto hover_path() -> const std::vector<tripoint_bub_ms> & { return hovered_route; } // *NOPAD*

auto hint() -> std::string { return hovered_hint; }

} // namespace tile_selection

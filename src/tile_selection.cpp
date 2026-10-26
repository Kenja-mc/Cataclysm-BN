#include "tile_selection.h"

#include <algorithm>
#include <optional>
#include <ranges>

#include "action.h"
#include "avatar.h"
#include "creature.h"
#include "map/field.h"
#include "map/field_type.h"
#include "game.h"
#include "gates.h"
#include "iexamine.h"
#include "input.h"
#include "item.h"
#include "line.h"
#include "map/map.h"
#include "messages.h"
#include "monster.h"
#include "mtype.h"
#include "npc.h"
#include "options.h"
#include "player_activity.h"
#include "smart_safemode.h"
#include "string_formatter.h"
#include "translations.h"
#include "trap.h"
#include "travel/travel_destination.h"
#include "ui.h"
#include "vehicle/vehicle.h"
#include "vehicle/vehicle_part.h"
#include "vehicle/vpart_position.h"

namespace
{

const auto trait_SHELL2 = trait_id( "SHELL2" );

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
    return m.route( you.bub_pos(), p, you.get_legacy_pathfinding_settings(),
    you.get_legacy_path_avoid() );
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

auto hotkey_for( const action_id act ) -> int
{
    switch( act ) {
    case ACTION_OPEN:
        return 'o';
    case ACTION_CLOSE:
        return 'c';
    case ACTION_EXAMINE:
        return 'e';
    case ACTION_PICKUP:
        return 'g';
    case ACTION_JUMP:
        return 'j';
    case ACTION_SMASH:
        return 'S';
    case ACTION_BUTCHER:
        return 'B';
    default:
        return MENU_AUTOASSIGN;
}
}

/// Lights up the tile of the highlighted menu row on the map.
class tile_highlight : public uilist_callback
{
public:
    explicit tile_highlight( const std::vector<tripoint_bub_ms> &tiles ) : tiles( tiles ) {
            draw = make_shared_fast<game::draw_callback_t>( [this]() {
                if( shown >= 0 && static_cast<size_t>( shown ) < this->tiles.size() ) {
                    get_map().drawsq( g->w_terrain, this->tiles[shown], drawsq_params().highlight( true ) );
                }
            } );
            g->add_draw_callback( draw );
        }
        void select( uilist *menu ) override {
            if( menu->selected != shown ) {
                shown = menu->selected;
                g->invalidate_main_ui_adaptor();
            }
        }
    private:
        const std::vector<tripoint_bub_ms> &tiles;
        shared_ptr_fast<game::draw_callback_t> draw;
        int shown = -1;
};

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
    if( dist == 0 && get_option<std::string>( "CONTROL_SCHEME" ) == "modern" ) {
        if( can_move_vertical_at( p, -1 ) ) {
            out.push_back( { .act = ACTION_MOVE_DOWN, .label = _( "descend" ) } );
        }
        if( can_move_vertical_at( p, 1 ) ) {
            out.push_back( { .act = ACTION_MOVE_UP, .label = _( "ascend" ) } );
        }
    }
    if( dist <= 1 && m.has_items( p ) && m.sees_some_items( p, you ) ) {
        out.push_back( { .act = ACTION_PICKUP, .label = _( "pick up items" ) } );
    } else if( dist <= 1 ) {
        // Like the door rules above, a cargo part with items is offered by its own presence; the
        // first part on the tile is the one pickup loots.
        if( const auto vp = m.veh_at( p ) ) {
            auto *const veh = veh_pointer_or_null( vp );
            const int cargo = veh ? veh->part_with_feature( vp->part_index(), "CARGO", false ) : -1;
            if( cargo >= 0 && !veh->get_items( cargo ).empty() ) {
                out.push_back( { .act = ACTION_PICKUP,
                                 .label = string_format( _( "get items from the %s" ),
                                     veh->part( cargo ).name() ),
                                 .vehicle_cargo = true } );
            }
        }
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

auto reachable( const avatar &you, const tripoint_bub_ms &p ) -> bool
{
    auto &m = get_map();
    return m.inbounds( p ) && p.z() == you.bub_pos().z() &&
           square_dist( p.xy(), you.bub_pos().xy() ) <= 1 &&
           !m.obstructed_by_vehicle_rotation( you.bub_pos(), p ) && you.sees( p );
}

auto interact_choices( const avatar &you, const tripoint_bub_ms &p,
                       const bool explicit_tile ) -> std::vector<choice>
{
    auto &m = get_map();
    const auto usable = [&]( const choice & c ) {
        return !c.travel && c.act != ACTION_ATTACK && c.act != ACTION_FIRE &&
               !( c.act == ACTION_PICKUP && you.is_mounted() );
    };
    auto out = choices_at( you, p ) | std::views::filter( usable ) | std::ranges::to<std::vector>();
    if( p == you.bub_pos() && can_examine_at( p ) ) {
        out.push_back( { .act = ACTION_EXAMINE, .label = string_format( _( "examine the %s" ), m.name( p ) ) } );
    }
    if( p == you.bub_pos() && !you.is_mounted() &&
    std::ranges::any_of( m.i_at( p ), []( const item * it ) { return it->is_corpse(); } ) ) {
        out.push_back( { .act = ACTION_BUTCHER, .label = _( "butcher a corpse" ) } );
    }
    if( p != you.bub_pos() ) {
        const auto obstacle = m.impassable( p ) || m.has_furn( p ) || m.move_cost( p ) > 2 ||
                              m.dangerous_field_at( p ) ||
                              ( you.knows_trap( p ) && !m.tr_at( p ).is_benign() );
        if( obstacle && iexamine::can_jump_over_tile( you, p ) ) {
            out.push_back( { .act = ACTION_JUMP, .label = string_format( _( "jump over the %s" ), m.name( p ) ) } );
        }
    }
    const auto pulpable = std::ranges::any_of( m.i_at( p ), []( const item * it ) {
        return it->is_corpse() && it->damage() < it->max_damage() &&
               ( it->can_revive() || it->get_mtype()->zombify_into );
    } );
    const auto bashable_field = std::ranges::any_of( m.field_at( p ), []( const auto & fd ) {
        return fd.first->bash_info.str_min != -1;
    } );
    // Every floor and wall is bashable, so a scan of the surroundings only offers the smashing
    // a player is likely to want; a tile the player picked offers it for anything.
    if( pulpable || bashable_field || ( explicit_tile && m.is_bashable( p ) ) ) {
        out.push_back( { .act = ACTION_SMASH, .label = string_format( _( "smash the %s" ), m.name( p ) ) } );
    }
    return out;
}

namespace
{

struct interaction {
    const choice &c;
    tripoint_bub_ms pos;
    const tile_actions &actions;
};

auto run_interaction( avatar &you, const interaction &what ) -> void
{
    const auto &p = what.pos;
    if( !reachable( you, p ) ) {
        return;
    }
    switch( what.c.act ) {
        case ACTION_MOVE_DOWN:
        case ACTION_MOVE_UP:
            what.actions.vertical( what.c.act );
            break;
        case ACTION_OPEN:
            open_at( p );
            break;
        case ACTION_EXAMINE:
            you.manual_examine = true;
            what.actions.examine( p );
            you.manual_examine = false;
            break;
        case ACTION_PICKUP:
            what.actions.pickup( p );
            break;
        case ACTION_CLOSE:
            if( you.is_mounted() && !you.mounted_creature->has_flag( MF_MOUNTABLE_DOORS ) ) {
                add_msg( m_info, _( "You can't close things while you're riding." ) );
            } else {
                doors::close_door( get_map(), you, p );
            }
            break;
        case ACTION_JUMP:
            iexamine::jump_over_tile( you, p );
            break;
        case ACTION_SMASH:
            smash_at( p );
            break;
        case ACTION_BUTCHER:
            if( you.has_active_mutation( trait_SHELL2 ) ) {
                add_msg( m_info, _( "You can't butcher while you're in your shell." ) );
            } else {
                what.actions.butcher();
            }
            break;
        default:
            break;
    }
}

/// Smashing and jumping are never done without asking.
auto runs_unasked( const choice &c ) -> bool
{
    return c.act != ACTION_SMASH && c.act != ACTION_JUMP;
}

/// How obviously a tile offers an action. Space runs the best rank and lists the rest, so the
/// order is the design: door, pickup, stairs, vehicle cargo, butcher, vault, examine, smash.
/// A vault only outranks an examine when there is an obstacle to vault over; bare floor is not one.
auto choice_rank( const choice &c, const bool obstacle ) -> int
{
    if( c.travel ) {
        return 90;
    }
    switch( c.act ) {
        case ACTION_OPEN:
        case ACTION_CLOSE:
            return 10;
        case ACTION_PICKUP:
            return c.vehicle_cargo ? 40 : 20;
        case ACTION_MOVE_DOWN:
        case ACTION_MOVE_UP:
            return 30;
        case ACTION_BUTCHER:
            return 50;
        case ACTION_JUMP:
            return obstacle ? 55 : 65;
        case ACTION_EXAMINE:
            return 60;
        case ACTION_SMASH:
            return 80;
        default:
            return 85;
    }
}

auto add_choice( std::vector<choice> &out, choice c ) -> void
{
    const auto already = [&c]( const choice & other ) {
        return other.act == c.act;
    };
    if( !std::ranges::any_of( out, already ) ) {
        out.push_back( std::move( c ) );
    }
}

/// The actions a right click lists for a tile in reach. Unlike an explicit Space click, bare
/// ground is left alone: every floor is bashable, but right-clicking open ground must only select.
auto clicked_choices_at( const avatar &you, const tripoint_bub_ms &p ) -> std::vector<choice>
{
    auto &m = get_map();
    auto out = interact_choices( you, p, false );
    const auto inside = !m.is_outside( you.bub_pos() );
    // Open doors count as flat ground, so name them with furniture as real objects.
    const auto door = m.can_open_door( &you, p, inside ) || m.close_door( p, inside, true );
    const auto solid = door || m.has_furn( p ) ||
                       ( m.is_bashable( p ) && !m.has_flag( "FLAT", p ) );
    const auto smashable = std::ranges::any_of( out, []( const choice & c ) {
        return c.act == ACTION_SMASH;
    } );
    if( solid && !smashable ) {
        add_choice( out, { .act = ACTION_SMASH,
                           .label = string_format( _( "smash the %s" ), m.name( p ) )
                         } );
    }
    return out;
}

/// Actions worth listing for a tile the player cannot reach: the reason is shown, not acted on.
auto distant_choices_at( const avatar &you, const tripoint_bub_ms &p ) -> std::vector<choice>
{
    auto &m = get_map();
    auto out = std::vector<choice>();
    if( p.z() != you.bub_pos().z() ) {
        return out;
    }
    if( m.can_open_door( &you, p, !m.is_outside( you.bub_pos() ) ) ) {
        add_choice( out, { .act = ACTION_OPEN, .label = string_format( _( "open the %s" ), m.name( p ) ) } );
    }
    if( m.close_door( p, !m.is_outside( you.bub_pos() ), true ) ) {
        add_choice( out, { .act = ACTION_CLOSE, .label = string_format( _( "close the %s" ), m.name( p ) ) } );
    }
    if( !you.is_mounted() && m.has_items( p ) && m.sees_some_items( p, you ) ) {
        add_choice( out, { .act = ACTION_PICKUP, .label = _( "pick up items" ) } );
    }
    if( can_examine_at( p ) ) {
        add_choice( out, { .act = ACTION_EXAMINE,
                           .label = string_format( _( "examine the %s" ), m.name( p ) )
                         } );
    }
    return out;
}

/// Displays the tile's actions and runs the picked one. Returns true when one ran.
auto show_interaction_menu( avatar &you, const tripoint_bub_ms &p, const tile_actions &actions,
                            std::vector<choice> choices, const bool in_reach ) -> bool
{
    auto menu = uilist();
    menu.text = string_format( _( "Interact with the %s" ), get_map().name( p ) );
    if( !in_reach ) {
        menu.text += "\n" + std::string( _( "You can't reach that tile." ) );
    }
    for( auto index = 0; const auto &c : choices ) {
        menu.addentry( index++, in_reach, hotkey_for( c.act ), c.label );
    }
    menu.query();
    if( in_reach && menu.ret >= 0 && static_cast<size_t>( menu.ret ) < choices.size() ) {
        run_interaction( you, { .c = choices[menu.ret], .pos = p, .actions = actions } );
        return true;
    }
    return false;
}

} // namespace

auto interact_at( avatar &you, const tripoint_bub_ms &p, const tile_actions &actions ) -> void
{
    if( !reachable( you, p ) ) {
    add_msg( _( "You can't reach that tile." ) );
        return;
    }
    auto choices = interact_choices( you, p, true );
    if( choices.empty() ) {
    add_msg( _( "There is nothing to interact with on that tile." ) );
        return;
    }
    const auto obstacle = get_map().impassable( p ) || get_map().has_furn( p ) ||
                          get_map().move_cost( p ) > 2;
    std::ranges::stable_sort( choices, [obstacle]( const choice & lhs, const choice & rhs ) {
        return choice_rank( lhs, obstacle ) < choice_rank( rhs, obstacle );
    } );
    const auto best = choices.front();
    const auto tied = std::ranges::count_if( choices, [&best, obstacle]( const choice & c ) {
        return choice_rank( c, obstacle ) == choice_rank( best, obstacle );
    } );
    // One obvious action runs. Everything else, a tie included, stays in the list.
    if( tied == 1 && runs_unasked( best ) ) {
        run_interaction( you, { .c = best, .pos = p, .actions = actions } );
        return;
    }
    // A lone vault over a real obstacle runs at once: the aim names the target, and the confirm
    // popup this replaced defaulted to No and answered to an uppercase Y only.
    if( tied == 1 && best.act == ACTION_JUMP && obstacle ) {
        run_interaction( you, { .c = best, .pos = p, .actions = actions } );
        return;
    }
    show_interaction_menu( you, p, actions, choices, true );
}

namespace
{

/// The first curtain part on a tile, with the vehicle it belongs to.
struct curtain_spot {
    vehicle *veh = nullptr;
    int part = -1;
};

auto curtain_at( map &m, const tripoint_bub_ms &p ) -> curtain_spot
{
    auto spot = curtain_spot();
    const auto vp = m.veh_at( p );
    spot.veh = veh_pointer_or_null( vp );
    if( spot.veh != nullptr ) {
        spot.part = spot.veh->part_with_feature( vp->part_index(), "CURTAIN", true );
    }
    return spot;
}

/// The state-aware toggle one chord press runs, with the same checks, wording and move costs as
/// walking into a vehicle door and closing it.
auto toggle_curtain( avatar &you, const curtain_spot &spot ) -> void
{
    const auto part_name = spot.veh->part( spot.part ).name();
    if( !spot.veh->is_open( spot.part ) ) {
        auto &m = get_map();
        if( veh_pointer_or_null( m.veh_at( you.bub_pos() ) ) != spot.veh &&
            spot.veh->part_flag( spot.part, "OPENCLOSE_INSIDE" ) ) {
            add_msg( m_info, _( "The %1$s's %2$s can only be opened from inside." ), spot.veh->name,
                     part_name );
            return;
        }
        if( !spot.veh->handle_potential_theft( you ) ) {
            return;
        }
        spot.veh->open( spot.part );
        add_msg( _( "You open the %1$s's %2$s." ), spot.veh->name, part_name );
        you.moves -= 100;
        return;
    }
    if( !spot.veh->handle_potential_theft( you ) ) {
        return;
    }
    if( !spot.veh->can_close( spot.part, you ) ) {
        return;
    }
    spot.veh->close( spot.part );
    add_msg( _( "You close the %1$s's %2$s." ), spot.veh->name, part_name );
    you.moves -= 90;
}

} // namespace

auto toggle_curtain_at( avatar &you, const tripoint_bub_ms &p ) -> void
{
    if( !reachable( you, p ) ) {
    add_msg( _( "You can't reach that tile." ) );
        return;
    }
    const auto spot = curtain_at( get_map(), p );
    if( spot.part < 0 ) {
    add_msg( m_info, _( "There is no curtain there." ) );
        return;
    }
    toggle_curtain( you, spot );
}

auto toggle_curtain_nearby( avatar &you ) -> bool
{
    struct curtain_option {
        tripoint_bub_ms pos;
        curtain_spot spot;
    };
    auto &m = get_map();
    auto spots = std::vector<curtain_option>();
    for( const auto &p : m.points_in_radius( you.bub_pos(), 1 ) ) {
        if( !reachable( you, p ) ) {
            continue;
        }
        auto spot = curtain_at( m, p );
        if( spot.part >= 0 ) {
            spots.push_back( { .pos = p, .spot = spot } );
        }
    }
    if( spots.empty() ) {
        return false;
    }
    if( spots.size() == 1 ) {
        toggle_curtain( you, spots.front().spot );
        return true;
    }
    auto tiles = spots | std::views::transform( &curtain_option::pos )
                 | std::ranges::to<std::vector>();
    auto highlight = tile_highlight( tiles );
    auto menu = uilist();
    menu.title = _( "Toggle which curtain?" );
    // The menu sits at the top so the highlighted tile next to the avatar stays visible.
    menu.w_y_setup = 0;
    menu.callback = &highlight;
    for( auto index = 0; const auto &option : spots ) {
        const auto &spot = option.spot;
        const auto where = option.pos == you.bub_pos() ? std::string( _( "here" ) ) :
                           direction_name( direction_from( you.bub_pos().xy(), option.pos.xy() ) );
        const auto doing = spot.veh->is_open( spot.part ) ? std::string( _( "close" ) ) :
                           std::string( _( "open" ) );
        menu.addentry( index++, true, MENU_AUTOASSIGN,
                       string_format( _( "%1$s the %2$s's %3$s (%4$s)" ), doing, spot.veh->name,
                                      spot.veh->part( spot.part ).name(), where ) );
    }
    menu.query();
    if( menu.ret >= 0 && static_cast<size_t>( menu.ret ) < spots.size() ) {
        toggle_curtain( you, spots[menu.ret].spot );
    }
    return true;
}

auto interact_menu_at( avatar &you, const tripoint_bub_ms &p, const tile_actions &actions ) -> bool
{
    // Right click never runs a lone action. A tile out of reach still lists what it offers,
    // disabled, so the player sees why the click did nothing else.
    const auto in_reach = reachable( you, p );
    if( !in_reach && ( p.z() != you.bub_pos().z() || !you.sees( p ) ) ) {
        return false;
    }
    auto choices = in_reach ? clicked_choices_at( you, p ) : distant_choices_at( you, p );
    if( choices.empty() ) {
        return false;
    }
    return show_interaction_menu( you, p, actions, std::move( choices ), in_reach );
}

auto interact_nearby( avatar &you, const tile_actions &actions ) -> bool
{
    struct directed_choice {
        tripoint_bub_ms pos;
        choice c;
    };
    auto options = std::vector<directed_choice>();
    for( const auto &p : get_map().points_in_radius( you.bub_pos(), 1 ) ) {
        if( !reachable( you, p ) ) {
            continue;
        }
        for( auto &c : interact_choices( you, p, false ) ) {
            options.push_back( { .pos = p, .c = std::move( c ) } );
        }
    }
    if( options.empty() ) {
        return false;
    }
    if( options.size() == 1 && runs_unasked( options.front().c ) ) {
        run_interaction( you, { .c = options.front().c, .pos = options.front().pos, .actions = actions } );
        return true;
    }
    auto tiles = options | std::views::transform( &directed_choice::pos ) |
                 std::ranges::to<std::vector>();
    auto highlight = tile_highlight( tiles );
    auto menu = uilist();
    menu.title = _( "Interact with what?" );
    // The menu sits at the top so the highlighted tile next to the avatar stays visible.
    menu.w_y_setup = 0;
    menu.callback = &highlight;
    for( auto index = 0; const auto &dc : options ) {
        const auto where = dc.pos == you.bub_pos() ? std::string( _( "here" ) ) :
                           direction_name( direction_from( you.bub_pos().xy(), dc.pos.xy() ) );
        //~ An action on a nearby tile and where it is, e.g. "open the door (north)".
        menu.addentry( index++, true, MENU_AUTOASSIGN, string_format( _( "%1$s (%2$s)" ), dc.c.label,
                where ) );
    }
    menu.query();
    if( menu.ret >= 0 && static_cast<size_t>( menu.ret ) < options.size() ) {
        const auto &picked = options[menu.ret];
        run_interaction( you, { .c = picked.c, .pos = picked.pos, .actions = actions } );
    }
    return true;
}

auto primary_choice( const avatar &you, const tripoint_bub_ms &p ) -> std::optional<choice>
{
    if( !reachable( you, p ) || has_hostile( you, p ) ) {
    return std::nullopt;
}
const auto choices = interact_choices( you, p, false );
const auto found = std::ranges::find_if( choices, runs_unasked );
return found == choices.end() ? std::nullopt : std::optional<choice>( *found );
}

auto has_hostile( const avatar &you, const tripoint_bub_ms &p ) -> bool
{
    return hostile_at( you, p ) != nullptr;
}

auto facing_tile( const avatar &you ) -> std::optional<tripoint_bub_ms>
{
    if( you.last_move_dir == tripoint_rel_ms::zero() ) {
        return std::nullopt;
    }
    return you.bub_pos() + you.last_move_dir;
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
        if( get_option<std::string>( "CONTROL_SCHEME" ) != "modern" ) {
            hovered_hint = _( "left: attack; right: select" );
        } else if( has_hostile( you, *p ) ) {
            hovered_hint = _( "left: attack; right: lock" );
        } else {
            // Reachable objects run their actions from the right click. Distant ones still list
            // them, disabled, so the hint must promise a menu rather than a plain selection.
            const auto actions = reachable( you, *p ) ? clicked_choices_at( you, *p ) :
                                 distant_choices_at( you, *p );
            const auto right = actions.empty() ? std::string( _( "right: select" ) ) :
                               std::string( _( "right: actions" ) );
            if( const auto primary = primary_choice( you, *p ) ) {
                //~ Mouse hint: what a left click does on the hovered tile, e.g. "left: open the door".
                hovered_hint = string_format( _( "left: %1$s; %2$s" ), primary->label, right );
            } else if( !actions.empty() ) {
                hovered_hint = right;
            } else {
                hovered_hint = _( "click: select" );
            }
        }
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

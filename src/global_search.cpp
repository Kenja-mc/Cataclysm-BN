#include "global_search.h"

#include <algorithm>
#include <array>
#include <cstddef>
#include <map>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "action_route.h"
#include "aim_reticle.h"
#include "avatar.h"
#include "color.h"
#include "creature.h"
#include "cursesdef.h"
#include "game.h"
#include "game_constants.h"
#include "ime.h"
#include "input.h"
#include "item.h"
#include "line.h"
#include "map/map.h"
#include "map/mapdata.h"
#include "map_memory.h"
#include "output.h"
#include "point.h"
#include "string_formatter.h"
#include "string_input_popup.h"
#include "string_utils.h"
#include "translations.h"
#include "trap.h"
#include "type_id.h"
#include "ui_manager.h"
#include "vehicle/veh_type.h"

namespace
{

/// The action a player binds to open the palette.  It stays in DEFAULTMODE so the keybindings
/// editor lists it next to the other map controls.
constexpr char search_action_id[] = "search_action";

/// Idents that are plumbing rather than something a player can pick from a search.
constexpr auto plumbing_actions = std::array{
    std::string_view( "ANY_INPUT" ), std::string_view( "COORDINATE" ),
    std::string_view( "MOUSE_MOVE" ), std::string_view( "SELECT" ),
    std::string_view( "SEC_SELECT" )
};

/// Screens whose keys belong to a text field, plus the palette itself.  The search key must not
/// steal a keystroke there, because the field would swallow the picked action.  A text field
/// registers the TEXT.* editing actions, which also catches uilist filter fields; the named
/// categories cover screens that build their context without them.
auto takes_free_text( const input_context &origin ) -> bool
{
    const auto &category = origin.get_category();
    if( category == "GLOBAL_SEARCH" || category == "STRING_INPUT" ||
        category == "STRING_EDITOR" || category == "HELP_KEYBINDINGS" ||
        category == "NEW_CHAR_DESCRIPTION" || category == "WORLDGEN_CONFIRM_DIALOG" ||
        category == "WAIT_FOR_ANY_KEY" ) {
        return true;
    }
    for( const auto &action : origin.get_registered_actions() ) {
        if( action == "TEXT.BACKSPACE" ) {
            return true;
        }
    }
    return false;
}

/// Matches kept after filtering, so one letter cannot fill the list with every floor tile.
constexpr std::size_t max_results = 300;

auto kind_rank( const global_search::target::kind type ) -> int
{
    switch( type ) {
        case global_search::target::kind::control:
            return 0;
        case global_search::target::kind::creature:
            return 1;
        case global_search::target::kind::sighted:
            return 2;
        case global_search::target::kind::remembered:
            return 3;
    }
    return 4;
}

auto kind_color( const global_search::target::kind type ) -> nc_color
{
    switch( type ) {
        case global_search::target::kind::control:
            return c_light_gray;
        case global_search::target::kind::creature:
            return c_light_red;
        case global_search::target::kind::sighted:
            return c_white;
        case global_search::target::kind::remembered:
            return c_light_blue;
    }
    return c_white;
}

/// Folds a name once per distinct name rather than once per tile.
class name_fold
{
    public:
        auto operator()( const std::string &name ) -> const std::string & {
            if( const auto found = folded_.find( name ); found != folded_.end() ) {
                return found->second;
            }
            return folded_.emplace( name, to_lower_case( name ) ).first->second;
        }

    private:
        std::map<std::string, std::string> folded_;
};

auto distinct( const std::vector<std::string> &names, const std::string &name ) -> bool
{
    return std::ranges::find( names, name ) == names.end();
}

/// "N", "NE" and so on, or nothing for the tile the player stands on.
auto distance_detail( const int distance, const direction dir ) -> std::string
{
    if( distance == 0 ) {
        return _( "here" );
    }
    return string_format( "%1$d %2$s", distance, direction_name_short( dir ) );
}

/// Turns a memorized terrain, furniture, trap or vehicle part id back into a player-visible name.
auto memorized_name( const std::string &id, const bool base ) -> std::string
{
    if( id.empty() ) {
        return std::string();
    }
    if( id.starts_with( "vp_" ) ) {
        const auto part = vpart_id( id.substr( 3 ) );
        return part.is_valid() ? part->name() : id.substr( 3 );
    }
    if( base ) {
        const auto ter = ter_str_id( id );
        return ter.is_valid() ? ter->name() : id;
    }
    if( const auto furn = furn_str_id( id ); furn.is_valid() ) {
        return furn->name();
    }
    if( const auto tr = trap_str_id( id ); tr.is_valid() ) {
        return tr->name();
    }
    if( const auto ter = ter_str_id( id ); ter.is_valid() ) {
        return ter->name();
    }
    return id;
}

auto by_distance( const global_search::target &lhs, const global_search::target &rhs ) -> bool
{
    return lhs.distance != rhs.distance ? lhs.distance < rhs.distance : lhs.label < rhs.label;
}

/// Everything on the player's own floor that they can see right now, nearest first.
auto sighted_targets( const avatar &you, map &here, name_fold &fold )
-> std::vector<global_search::target>
{
    auto out = std::vector<global_search::target>();
    for( const tripoint_bub_ms &p :
         closest_points_generator( you.bub_pos(), g_max_view_distance ) ) {
        const int distance = rl_dist( you.bub_pos(), p );
        if( !here.inbounds( p ) || !you.sees( p ) ) {
            continue;
        }
        const auto terrain = here.tername( p );
        const auto furnished = here.has_furn( p );
        const auto base = furnished ? here.furnname( p ) : terrain;
        auto extras = std::vector<std::string>();
        if( furnished && base != terrain ) {
            extras.push_back( terrain );
        }
        const auto &tr = here.tr_at( p );
        if( tr.loadid && tr.can_see( p, you ) && distinct( extras, tr.name() ) ) {
            extras.push_back( tr.name() );
        }
        if( here.sees_some_items( p, you ) ) {
            std::size_t shown = 0;
            for( const auto *it : here.i_at( p ) ) {
                const auto name = it->tname();
                if( name == base || !distinct( extras, name ) ) {
                    continue;
                }
                extras.push_back( name );
                if( ++shown == 4 ) {
                    break;
                }
            }
        }
        auto target = global_search::target();
        target.type = global_search::target::kind::sighted;
        target.label = base;
        target.match_text = fold( base );
        for( const std::string &extra : extras ) {
            target.label += " · " + extra;
            target.match_text += " " + fold( extra );
        }
        target.pos = p;
        target.distance = distance;
        target.selectable = true;
        target.detail = distance_detail( target.distance,
                                         direction_from( you.bub_pos().raw(), p.raw() ) );
        out.push_back( std::move( target ) );
    }
    return out;
}

/// Every creature the compass would show the player, nearest first.
auto creature_targets( const avatar &you, map &here, name_fold &fold )
-> std::vector<global_search::target>
{
    auto out = std::vector<global_search::target>();
    for( const auto *critter : you.get_visible_creatures( g_mapsize_x ) ) {
        const tripoint_bub_ms p = critter->bub_pos();
        auto target = global_search::target();
        target.type = global_search::target::kind::creature;
        target.label = critter->disp_name();
        target.match_text = fold( target.label );
        target.pos = p;
        target.distance = rl_dist( you.bub_pos(), p );
        target.selectable = p.z() == you.bub_pos().z() && here.inbounds( p );
        target.detail = string_format( _( "%1$s, seen" ),
                                       distance_detail( target.distance,
                                               direction_from( you.bub_pos().raw(), p.raw() ) ) );
        out.push_back( std::move( target ) );
    }
    std::ranges::sort( out, by_distance );
    return out;
}

/// What map memory holds nearby and the player cannot see any more: the whole point of a
/// remembered search.  Only tiles the view can pan onto are listed, and only what memory holds is
/// ever named — never what stands there now.
auto remembered_targets( const avatar &you, map &here, name_fold &fold )
-> std::vector<global_search::target>
{
    auto out = std::vector<global_search::target>();
    const auto bubble_start = tripoint_bub_ms( 0, 0, you.bub_pos().z() );
    const auto bubble_min = project_to<coords::sm>( bub_to_abs( bubble_start ) );
    const auto bubble_max = bubble_min + tripoint( g_mapsize - 1, g_mapsize - 1, 0 );
    for( const memorized_tile &tile : you.map_memory_data().memorized_tiles( bubble_min,
            bubble_max ) ) {
        const tripoint_bub_ms p = abs_to_bub( tile.pos );
        if( p.z() != you.bub_pos().z() || !here.inbounds( p ) ) {
            // Outside the loaded bubble there is nothing to draw and nothing to pan to.
            continue;
        }
        const int distance = rl_dist( you.bub_pos(), p );
        if( you.sees( p ) ) {
            continue;    // the live scan already lists what is there now
        }
        const auto overlay = memorized_name( tile.overlay.tile, false );
        const auto base = memorized_name( tile.base.tile, true );
        std::string label;
        if( overlay.empty() ) {
            label = base;
        } else if( base.empty() || base == overlay ) {
            label = overlay;
        } else {
            //~ A remembered furniture or trap on top of the remembered ground beneath it.
            label = string_format( _( "%1$s on %2$s" ), overlay, base );
        }
        if( label.empty() ) {
            continue;
        }
        auto target = global_search::target();
        target.type = global_search::target::kind::remembered;
        target.label = label;
        target.match_text = fold( label );
        target.pos = p;
        target.distance = distance;
        // The view pans onto the memory; the targeting reticle is never put on unseen ground.
        target.selectable = true;
        target.detail = string_format( _( "%1$s, remembered" ),
                                       distance_detail( distance,
                                               direction_from( you.bub_pos().raw(), p.raw() ) ) );
        out.push_back( std::move( target ) );
    }
    // Every remembered tile of the loaded bubble stays searchable; the cap that used to apply
    // here ran before the query, so a distant landmark could never be found.
    std::ranges::sort( out, by_distance );
    return out;
}

/// The controls the current screen handles.  Matches are sorted by name later, so this order is
/// only the tie-breaker before that sort.
auto control_targets( const input_context &origin, name_fold &fold )
-> std::vector<global_search::target>
{
    auto out = std::vector<global_search::target>();
    const auto &category = origin.get_category();
    for( const std::string &ident : origin.get_registered_actions() ) {
        const auto plumbing = std::ranges::find( plumbing_actions, std::string_view( ident ) );
        const bool is_plumbing = plumbing != plumbing_actions.end();
        if( ident == search_action_id || is_plumbing ) {
            continue;
        }
        auto target = global_search::target();
        target.type = global_search::target::kind::control;
        target.ident = ident;
        target.label = origin.get_action_name( ident );
        target.detail = action_route( ident, category );
        target.match_text = fold( target.label + " " + ident + " " + target.detail );
        out.push_back( std::move( target ) );
    }
    return out;
}

struct hit {
    const global_search::target *target = nullptr;
    int score = 0;
};

/// Every term has to appear in the already folded text.  The score prefers a name that starts
/// with a term over one that merely contains it, so the best match comes first.
auto matches_query( const std::string &folded_text, const std::vector<std::string> &terms,
                    int &score ) -> bool
{
    score = 0;
    for( const auto &term : terms ) {
        const std::size_t pos = folded_text.find( term );
        if( pos == std::string::npos ) {
            return false;
        }
        score += pos == 0 ? 0 : 1;
    }
    return true;
}

auto hit_less( const hit &lhs, const hit &rhs ) -> bool
{
    if( lhs.score != rhs.score ) {
        return lhs.score < rhs.score;
    }
    const auto lhs_rank = kind_rank( lhs.target->type );
    const auto rhs_rank = kind_rank( rhs.target->type );
    if( lhs_rank != rhs_rank ) {
        return lhs_rank < rhs_rank;
    }
    if( lhs.target->distance != rhs.target->distance ) {
        return lhs.target->distance < rhs.target->distance;
    }
    return lhs.target->label < rhs.target->label;
}

} // namespace

namespace global_search
{

auto opens_here( const input_event &evt, const input_context &origin ) -> bool
{
    // Keyboard and gamepad alike; a menu pick returns an action string either way.
    if( ( evt.type != input_event_t::keyboard && evt.type != input_event_t::gamepad ) ||
        evt.sequence.empty() ) {
        return false;
    }
    if( g != nullptr && g->uquit == QUIT_WATCH ) {
        return false;    // the death cam must not gain cursor control
    }
    if( takes_free_text( origin ) ) {
        return false;
    }
    // Menus do not register the action and their contexts carry no binding of their own, so the
    // map's key is the one binding to consult.  Looking it up in the screen's own context would
    // make the input manager create a placeholder entry for every screen we pass through.
    for( const input_event &bound :
         inp_mngr.get_input_for_action( std::string( search_action_id ), "DEFAULTMODE" ) ) {
        if( bound == evt ) {
            return true;
        }
    }
    return false;
}

auto map_targets( const avatar &you, map &here ) -> std::vector<target>
{
    name_fold fold;
    std::vector<target> out = sighted_targets( you, here, fold );
    const std::vector<target> creatures = creature_targets( you, here, fold );
    out.insert( out.end(), creatures.begin(), creatures.end() );
    const std::vector<target> remembered = remembered_targets( you, here, fold );
    out.insert( out.end(), remembered.begin(), remembered.end() );
    return out;
}

auto focus( const target &what ) -> bool
{
    if( g == nullptr || what.type == target::kind::control ) {
        return false;
    }
    avatar &you = g->u;
    map &here = get_map();
    if( what.pos.z() != you.bub_pos().z() || !here.inbounds( what.pos ) ) {
        return false;
    }
    if( what.type == target::kind::remembered ) {
        // The view is the cursor for a remembered tile.  The targeting reticle is cleared first:
        // a reticle is an attack target, so leaving one on other ground while the view moves to
        // memory could make the next attack fire somewhere the player is not looking.  The tile
        // inspector is closed for the same reason: it would read the live map instead of the
        // memory the player is being shown.
        aim_reticle::clear();
        g->hide_tile_preview();
        you.view_offset = what.pos - you.bub_pos();
        g->invalidate_main_ui_adaptor();
        return true;
    }
    if( you.view_offset != tripoint_rel_ms::zero() ) {
        you.view_offset = tripoint_rel_ms::zero();
        g->invalidate_main_ui_adaptor();
    }
    if( !aim_reticle::select( you, here, what.pos ) ) {
        return false;
    }
    g->show_tile_preview( what.pos );
    g->invalidate_main_ui_adaptor();
    return true;
}

auto run( const input_context &origin ) -> std::string
{
    const bool map_scope = g != nullptr && origin.get_category() == "DEFAULTMODE";
    name_fold fold;
    const std::vector<target> controls = control_targets( origin, fold );
    // The world is scanned on the first typed character, not when the box opens: an empty
    // search lists nothing, so the scan would only delay the first frame.
    std::vector<target> world;
    bool world_built = false;
    // Everything the palette may move, so canceling or running a control can put it back.
    const tripoint_rel_ms opening_offset = map_scope ? g->u.view_offset : tripoint_rel_ms::zero();
    const std::optional<tripoint_bub_ms> opening_reticle =
        map_scope ? aim_reticle::pos() : std::nullopt;
    const std::optional<tripoint_bub_ms> opening_preview =
        map_scope ? g->tile_preview_position() : std::nullopt;
    bool previewed = false;

    std::vector<hit> matches;
    std::size_t selected = 0;
    std::size_t scroll = 0;
    std::string last_query;

    /// Undoes a preview: the map shows the cursor the screen had before the search.
    const auto restore_cursor = [&]() {
        if( !map_scope || !previewed ) {
            return;
        }
        avatar &you = g->u;
        you.view_offset = opening_offset;
        if( !opening_reticle || !aim_reticle::select( you, get_map(), *opening_reticle ) ) {
            aim_reticle::clear();
        }
        if( opening_preview ) {
            g->show_tile_preview( *opening_preview );
        } else {
            g->hide_tile_preview();
        }
        previewed = false;
        g->invalidate_main_ui_adaptor();
    };

    /// Puts the existing cursor on the selected row; a row without one undoes the last preview.
    const auto preview = [&]() {
        if( !map_scope ) {
            return;
        }
        if( !matches.empty() && matches[selected].target->selectable &&
            focus( *matches[selected].target ) ) {
            previewed = true;
            return;
        }
        restore_cursor();
    };

    const auto rebuild = [&]( const std::string &query ) {
        const std::string folded_query = to_lower_case( query );
        std::vector<std::string> terms;
        for( const std::string &term : string_split( folded_query, ' ' ) ) {
            if( !term.empty() ) {
                terms.push_back( term );
            }
        }
        matches.clear();
        selected = 0;
        scroll = 0;
        if( terms.empty() ) {
            // A search box with nothing typed lists nothing, so Enter cannot run a guess.
            restore_cursor();
            return;
        }
        if( map_scope && !world_built ) {
            world = map_targets( g->u, get_map() );
            world_built = true;
        }
        const auto add = [&]( const std::vector<target> &pool ) {
            for( const target &candidate : pool ) {
                hit entry;
                entry.target = &candidate;
                if( !matches_query( candidate.match_text, terms, entry.score ) ) {
                    continue;
                }
                matches.push_back( entry );
            }
        };
        add( controls );
        add( world );
        std::ranges::sort( matches, hit_less );
        if( matches.size() > max_results ) {
            matches.resize( max_results );
        }
        preview();
    };

    rebuild( last_query );

    input_context ctxt( "GLOBAL_SEARCH" );
    ctxt.register_action( "UP" );
    ctxt.register_action( "DOWN" );
    ctxt.register_action( "PAGE_UP" );
    ctxt.register_action( "PAGE_DOWN" );
    ctxt.register_action( "NEXT_TAB" );
    ctxt.register_action( "PREV_TAB" );
    ctxt.register_action( "CONFIRM" );
    ctxt.register_action( "QUIT" );
    ctxt.register_action( "TEXT.LEFT" );
    ctxt.register_action( "TEXT.RIGHT" );
    ctxt.register_action( "TEXT.CLEAR" );
    ctxt.register_action( "TEXT.BACKSPACE" );
    ctxt.register_action( "TEXT.HOME" );
    ctxt.register_action( "TEXT.END" );
    ctxt.register_action( "TEXT.DELETE" );
#if defined( TILES )
    ctxt.register_action( "TEXT.PASTE" );
#endif
    ctxt.register_action( "TEXT.INPUT_FROM_FILE" );
    ctxt.register_action( "ANY_INPUT" );

    string_input_popup spopup;
    spopup.context( ctxt ).max_length( 200 );

    int width = 0;
    int height = 0;
    catacurses::window w;

    ui_adaptor ui;
    const auto recalc_size = [&]( ui_adaptor & adaptor ) {
        const auto max_width = std::max( FULL_SCREEN_WIDTH, TERMX );
        const auto max_height = std::max( FULL_SCREEN_HEIGHT, TERMY );
        width = std::min( 88, max_width );
        height = std::min( 22, max_height );
        // The Mouse View preview takes the upper half of the screen, so the map palette sits low.
        const auto top = map_scope ? max_height - height : max_height / 2 - height / 2;
        w = catacurses::newwin( height - 2, width - 2, point( max_width / 2 - width / 2, top ) );
        spopup.window( w, point( 4, 4 ), getmaxx( w ) - 3 );
        adaptor.position_from_window( w );
    };
    recalc_size( ui );
    ui.on_screen_resize( recalc_size );

    const auto redraw = [&]( ui_adaptor &adaptor ) {
        werase( w );
        draw_border( w, BORDER_COLOR, _( "Search" ), c_light_red );
        const int inner_width = getmaxx( w ) - 4;
        const std::string hint =
            _( "Controls of this screen, detected creatures, seen or remembered tiles." );
        trim_and_print( w, point( 2, 1 ), inner_width, c_light_gray, "%s", hint );
        const std::string keys =
            _( "Tab: next · Shift+Tab: previous · Enter: run or select · Esc: close" );
        trim_and_print( w, point( 2, 2 ), inner_width, c_dark_gray, "%s", keys );
        mvwprintz( w, point( 2, 4 ), c_light_gray, ">" );
        const int list_top = 6;
        const int list_bottom = getmaxy( w ) - 2;
        const int visible_rows = std::max( 1, list_bottom - list_top );
        if( selected < scroll ) {
            scroll = selected;
        } else if( selected >= scroll + static_cast<std::size_t>( visible_rows ) ) {
            scroll = selected - static_cast<std::size_t>( visible_rows ) + 1;
        }
        const int name_width = std::max( 10, getmaxx( w ) * 3 / 5 );
        const int detail_width = std::max( 6, inner_width - name_width );
        for( int row = 0; row < visible_rows; row++ ) {
            const std::size_t index = scroll + static_cast<std::size_t>( row );
            if( index >= matches.size() ) {
                break;
            }
            const target &picked = *matches[index].target;
            const bool active = index == selected;
            const nc_color name_color = active ? hilite( kind_color( picked.type ) ) :
                                       kind_color( picked.type );
            const nc_color detail_color = active ? hilite( c_dark_gray ) : c_dark_gray;
            const point row_pos( 2, list_top + row );
            trim_and_print( w, row_pos, name_width, name_color, "%s", picked.label );
            trim_and_print( w, row_pos + point( name_width + 1, 0 ), detail_width, detail_color,
                            "%s", picked.detail );
        }
        std::string status;
        if( matches.empty() ) {
            status = last_query.empty() ? _( "Type to search." ) : _( "Nothing matches." );
        } else {
            status = string_format( "%1$d/%2$d", static_cast<int>( selected + 1 ),
                                    static_cast<int>( matches.size() ) );
        }
        mvwprintz( w, point( 2, getmaxy( w ) - 2 ), c_dark_gray, "%s", status );
        // The input line has to be drawn last: it places the terminal cursor.
        spopup.text( last_query );
        spopup.query_string( false, true );
        adaptor.record_term_cursor();
    };
    ui.on_redraw( redraw );

    // Keep the input method out of the way, as every other text field in a loop does.
    ime_sentry sentry( ime_sentry::keep );

    std::string chosen;
    while( true ) {
        ui_manager::redraw();
        const std::string query = spopup.query_string( false );
        const std::string action = ctxt.input_to_action( ctxt.get_raw_input() );
        if( query != last_query ) {
            last_query = query;
            rebuild( last_query );
        }
        if( action == "QUIT" ) {
            restore_cursor();
            break;
        }
        if( action == "CONFIRM" ) {
            if( matches.empty() ) {
                restore_cursor();
            } else {
                const target &picked = *matches[selected].target;
                if( picked.type == target::kind::control ) {
                    // Running a control is not a map pick, so put the map cursor back first.
                    chosen = picked.ident;
                    restore_cursor();
                } else {
                    // A map pick leaves the cursor where the preview put it.
                    preview();
                }
            }
            break;
        }
        const auto move_selection = [&]( const int delta ) {
            if( matches.empty() ) {
                return;
            }
            const int count = static_cast<int>( matches.size() );
            int next = static_cast<int>( selected ) + delta;
            next = ( next % count + count ) % count;
            selected = static_cast<std::size_t>( next );
            preview();
        };
        if( action == "DOWN" || action == "NEXT_TAB" ) {
            move_selection( 1 );
        } else if( action == "UP" || action == "PREV_TAB" ) {
            move_selection( -1 );
        } else if( action == "PAGE_DOWN" ) {
            move_selection( 10 );
        } else if( action == "PAGE_UP" ) {
            move_selection( -10 );
        }
    }

    return chosen;
}

} // namespace global_search

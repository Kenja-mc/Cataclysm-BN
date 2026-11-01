#include "hud_fusion.h"

#include <algorithm>
#include <array>
#include <optional>
#include <ranges>
#include <string>
#include <vector>

#include "action.h"
#include "avatar.h"
#include "cached_options.h"
#include "catacharset.h"
#include "cursesdef.h"
#include "hud_draw.h"
#include "game.h"
#include "hotbar.h"
#include "hud_boxes.h"
#include "hud_snapshot.h"
#include "input.h"
#include "options.h"
#include "output.h"
#include "panels.h"
#include "string_formatter.h"
#include "translations.h"

namespace hud_fusion
{

namespace
{

using namespace hud_draw;

constexpr auto deck_height = 7;

/// Icon, the need's name and its state; an unmet need replaces "ok" with its own wording.
struct hit_area {
    rect at;
    /// Hotbar slot index, or -1 for an overlay that only swallows the click.
    int slot = -1;
};
/// Where the last frame drew its overlays, in map-window cells, for click handling.
auto hits = std::vector<hit_area>();

auto need( const catacurses::window &w, const point at, const char *icon, const nc_color icon_color,
           const hud_snapshot::need &n ) -> void
{
    auto x = text( w, at, icon_color, icon );
    if( n.fine ) {
        x = text( w, point( x + 1, at.y ), pal::muted(), n.label + " " );
        text( w, point( x, at.y ), pal::muted(), _( "ok" ) );
    } else {
        text( w, point( x + 1, at.y ), n.color, n.text );
    }
}

struct vital_options {
    int y = 0;
    const char *icon = "";
    nc_color color = c_white;
    int value = 0;
    int max = 1;
    std::string label;
};

auto vital( const catacurses::window &w, const vital_options &opts ) -> void
{
    text( w, point( 2, opts.y ), opts.color, opts.icon );
    bar( w, { .at = point( 4, opts.y ), .width = 14, .value = opts.value, .max = opts.max, .fill = opts.color } );
    text( w, point( 20, opts.y ), pal::text(), opts.label );
}

auto draw_ribbon( const canvas &area, const hud_snapshot::snapshot &s ) -> void
{
    hits.push_back( { .at = { .at = point_zero, .width = area.width, .height = 1 } } );
    const auto w = panel( area, { .at = point_zero, .width = area.width, .height = 1 } );
    auto x = text( w, point( 1, 0 ), pal::title(), s.date + " " + s.time );
    x = dot( w, point( x, 0 ) );
    x = text( w, point( x, 0 ), s.weather_color, s.weather );
    x = dot( w, point( x, 0 ) );
    x = text( w, point( x, 0 ), s.light_color, s.light );
    x = dot( w, point( x, 0 ) );
    x = text( w, point( x, 0 ), s.wind_color, s.wind );
    if( s.safe_mode ) {
        x = dot( w, point( x, 0 ) );
        text( w, point( x, 0 ), s.safe_color, string_format( "%s %s", glyph::safe, _( "safe" ) ) );
    }
}

/// The first key bound to `act` on the map, empty when unbound.
auto key_for( const action_id act ) -> std::string
{
    const auto ctxt = input_context( "DEFAULTMODE" );
    if( ctxt.key_bound_to( action_ident( act ), 0, false ).empty() ) {
        return {};
    }
    const auto desc = ctxt.get_desc( action_ident( act ), 1 );
    return desc == inp_mngr.get_keyname( ' ', input_event_t::keyboard ) ? std::string( _( "spc" ) ) : desc;
}

/// The handful of keys a player needs most, with their live bindings, on one row.
auto draw_hints( const catacurses::window &w, const point at, const int room ) -> void
{
    struct entry {
        std::vector<action_id> acts;
        const char *label;
        /// Join the first and last key as "1-6" instead of running them together.
        bool range = false;
    };
    static const auto entries = std::array<entry, 11> { {
            { { ACTION_MOVE_FORTH, ACTION_MOVE_LEFT, ACTION_MOVE_BACK, ACTION_MOVE_RIGHT }, translate_marker( "move" ) },
            { { ACTION_HOTBAR_1, ACTION_HOTBAR_6 }, translate_marker( "hotbar" ), true },
            { { ACTION_HOTBAR_ASSIGN }, translate_marker( "assign slot" ) },
            { { ACTION_EXAMINE }, translate_marker( "interact" ) },
            { { ACTION_INVENTORY }, translate_marker( "inventory" ) },
            { { ACTION_ACTIONMENU }, translate_marker( "menus" ) },
            { { ACTION_KEYBINDINGS }, translate_marker( "all keys" ) },
            { { ACTION_FIRE }, translate_marker( "attack" ) },
            { { ACTION_PICKUP }, translate_marker( "pick up" ) },
            { { ACTION_PAUSE }, translate_marker( "wait" ) },
            { { ACTION_MAP }, translate_marker( "map" ) },
        }
    };
    auto x = at.x;
    for( const auto &e : entries ) {
        auto keys = std::string();
        for( const auto act : e.acts ) {
            keys += ( e.range && !keys.empty() ? "-" : "" ) + key_for( act );
        }
        if( keys.empty() ) {
            continue;
        }
        if( x + width( keys ) + 1 + utf8_width( _( e.label ) ) > at.x + room ) {
            break;
        }
        x = text( w, point( x, at.y ), pal::heading(), keys );
        x = text( w, point( x + 1, at.y ), pal::muted(), _( e.label ) ) + 3;
    }
}

auto draw_vehicle( const avatar &you, const canvas &area ) -> void
{
    const auto rows = hud_boxes::vehicle_rows( you );
    if( rows.empty() ) {
        return;
    }
    const auto height = static_cast<int>( rows.size() ) + 2;
    hits.push_back( { .at = { .at = point( 0, area.height - deck_height - height ), .width = 32, .height = height } } );
    const auto w = panel( area, {
        .at = point( 0, area.height - deck_height - height ), .width = 32, .height = height
    } );
    card( w, { .title = _( "VEHICLE" ) } );
    for( auto i = 0; i < static_cast<int>( rows.size() ); ++i ) {
        text( w, point( 2, 1 + i ), rows[static_cast<size_t>( i )].color, rows[static_cast<size_t>( i )].text );
    }
}

auto draw_deck( const avatar &you, const canvas &area, const hud_snapshot::snapshot &s ) -> void
{
    hits.push_back( { .at = { .at = point( 0, area.height - deck_height ), .width = area.width, .height = deck_height } } );
    const auto w = panel( area, {
        .at = point( 0, area.height - deck_height ), .width = area.width, .height = deck_height
    } );
    card( w, { .title = _( "LOADOUT" ), .summary = string_format( "%s kg  %s L", s.weight, s.volume ),
               .summary_color = pal::muted() } );

    // The weapon card; the item's map symbol stands in for its tile.
    text( w, point( 2, 1 ), pal::border(), "╭─────╮" );
    text( w, point( 2, 2 ), pal::border(), "│     │" );
    text( w, point( 2, 3 ), pal::border(), "╰─────╯" );
    text( w, point( 5, 2 ), s.weapon_color, s.weapon_symbol );
    constexpr auto weapon_room = 20;
    text( w, point( 10, 1 ), pal::title(), utf8_truncate( s.weapon, weapon_room ) );
    auto x = 10;
    if( s.gun ) {
        x = text( w, point( x, 2 ), pal::accent(), s.ammo );
        x = dot( w, point( x, 2 ) );
    }
    if( s.armed ) {
        text( w, point( x, 2 ), pal::text(), glyph::weapon );
    }
    text( w, point( 10, 3 ), pal::muted(), utf8_truncate( s.style.empty() ? s.stance : s.style, weapon_room ) );

    // Hotbar: six boxes, the key in the top edge, the item's symbol and name inside.
    constexpr auto slot_x = 32;
    const auto room = area.width - slot_x - 2;
    const auto box_w = std::clamp( room / hotbar::slots, 9, 16 );
    const auto any_assigned = std::ranges::any_of( std::views::iota( 0, hotbar::slots ), [&]( const int i ) {
        return hotbar::view( you, i ).assigned;
    } );
    if( !any_assigned ) {
        // Six empty boxes teach nothing; say what the slots are for and how to fill them.
        const auto assign = key_for( ACTION_HOTBAR_ASSIGN );
        text( w, point( slot_x, 1 ), pal::heading(), _( "HOTBAR" ) );
        text( w, point( slot_x, 2 ), pal::muted(), assign.empty() ?
              _( "Assign items from Enter → Misc → Assign a hotbar slot, then use them with 1–6." ) :
              string_format( _( "Press %s to put an item in a slot, then use it with 1–6 or a click." ), assign ) );
    }
    for( auto i = 0; any_assigned && i < hotbar::slots; ++i ) {
        const auto v = hotbar::view( you, i );
        const auto sx = slot_x + i * box_w;
        hits.push_back( { .at = { .at = point( sx, area.height - deck_height + 1 ), .width = box_w - 1, .height = 3 },
                          .slot = i } );
        const auto ready = v.assigned && v.count > 0;
        const auto color = v.wielded ? pal::accent() : ready ? pal::text() : pal::border();
        hline( w, point( sx + 1, 1 ), box_w - 3, color );
        hline( w, point( sx + 1, 3 ), box_w - 3, color );
        text( w, point( sx, 1 ), color, "╭" );
        text( w, point( sx + box_w - 2, 1 ), color, "╮" );
        text( w, point( sx, 2 ), color, "│" );
        text( w, point( sx + box_w - 2, 2 ), color, "│" );
        text( w, point( sx, 3 ), color, "╰" );
        text( w, point( sx + box_w - 2, 3 ), color, "╯" );
        text( w, point( sx + 2, 1 ), v.wielded ? pal::accent() : pal::heading(), std::to_string( i + 1 ) );
        if( !v.assigned ) {
            text( w, point( sx + 2, 2 ), pal::border(), "·" );
            continue;
        }
        text( w, point( sx + 2, 2 ), ready ? v.color : pal::border(), v.symbol );
        const auto label = v.name + ( v.count > 1 ? " x" + std::to_string( v.count ) : std::string() );
        text( w, point( sx + 4, 2 ), ready ? pal::title() : pal::muted(), utf8_truncate( label, box_w - 7 ) );
    }

    hline( w, point( 2, 4 ), area.width - 4, pal::border() );
    draw_hints( w, point( 2, 5 ), area.width - 4 );
}

/// Read once per map frame by the overlays and reused by the sidebar sections drawn after them.
auto cache = std::optional<hud_snapshot::snapshot>();

auto refresh( const avatar &you ) -> const hud_snapshot::snapshot & // *NOPAD*
{
    cache = hud_snapshot::read( you );
    return *cache;
}

auto current( const avatar &you ) -> const hud_snapshot::snapshot & // *NOPAD*
{
    return cache ? *cache : refresh( you );
}

/// Every sidebar section draws a left edge, so the column reads as one sidebar.
auto edge( const catacurses::window &w ) -> void
{
    werase( w );
    vline( w, point_zero, getmaxy( w ), pal::border() );
}

/// The STATUS section: the bars, the needs, and what the old Movement panel read. It sits in the
/// column so nothing covers the map.
auto status_section( const catacurses::window &w, const hud_snapshot::snapshot &s ) -> void
{
    edge( w );
    rule( w, { .title = _( "STATUS" ), .summary = s.stance, .summary_color = s.stance_color } );
    const auto stamina = s.stamina_max > 0 ? s.stamina * 100 / s.stamina_max : 0;
    vital( w, { .y = 1, .icon = glyph::hp, .color = s.hp_color, .value = s.hp_percent, .max = 100,
                .label = string_format( _( "Health %d%%" ), s.hp_percent ) } );
    vital( w, { .y = 2, .icon = glyph::stamina, .color = pal::stamina(), .value = s.stamina,
                .max = s.stamina_max, .label = string_format( _( "Stamina %d%%" ), stamina ) } );
    vital( w, { .y = 3, .icon = glyph::focus, .color = pal::focus(), .value = s.focus, .max = 100,
                .label = string_format( _( "Focus %d" ), s.focus ) } );
    // Mood changes how fast you learn and whether you can craft, so it sits beside the bars.
    text( w, point( 32, 3 ), s.morale < -10 ? pal::danger() : s.morale > 10 ? c_light_green : pal::muted(),
          string_format( _( "Mood %+d" ), s.morale ) );
    text( w, point( 2, 4 ), s.pain_level > 0 ? pal::danger() : pal::muted(),
          string_format( _( "%s Pain %d" ), glyph::pain, s.pain_level ) );
    text( w, point( 12, 4 ), pal::muted(), string_format( _( "Speed %d  Noise %s" ), s.speed, s.sound ) );
    need( w, point( 2, 5 ), glyph::thirst, pal::thirst(), s.thirst );
    need( w, point( 20, 5 ), glyph::rest, pal::rest(), s.rest );
    need( w, point( 2, 6 ), glyph::hunger, pal::hunger(), s.hunger );
    need( w, point( 20, 6 ), glyph::heat, pal::heat(), s.heat );
    text( w, point( 2, 7 ), pal::muted(), string_format( "Str %d  Dex %d  Int %d  Per %d", s.str, s.dex, s.intel, s.per ) );
}

} // namespace

auto body_rows( const avatar &you ) -> int
{
    // Every limb keeps its own bar: a single "no wounds" line hides the one that just got hit.
    return 1 + static_cast<int>( current( you ).limbs.size() );
}

auto around_rows( const avatar &you ) -> int
{
    return 1 + std::clamp( static_cast<int>( current( you ).seen.size() ), 0, 4 );
}

auto minimap_rows() -> int
{
#if defined(TILES)
    if( !pixel_minimap_option ) {
        return 0;
    }
    const auto chosen = get_option<int>( "PIXEL_MINIMAP_HEIGHT" );
    // The layout's own default when the player has not set a height: compact, so the log grows.
    return chosen > 0 ? chosen : 12;
#else
    return 0;
#endif
}

auto fits() -> bool { return TERMX >= 140 && TERMY >= 36; }

auto active() -> bool
{
    return panel_manager::get_manager().get_current_layout_id() == "fusion";
}

auto draw( const avatar &you, const catacurses::window &w_terrain ) -> void
{
    if( !active() ) {
        return;
    }
    const auto area = canvas{
        .origin = point( getbegx( w_terrain ), getbegy( w_terrain ) ),
        .width = is_draw_tiles_mode() ? TERRAIN_WINDOW_TERM_WIDTH : getmaxx( w_terrain ),
        .height = is_draw_tiles_mode() ? TERRAIN_WINDOW_TERM_HEIGHT : getmaxy( w_terrain ),
    };
    const auto &s = refresh( you );
    hits.clear();
    begin_frame();
    draw_ribbon( area, s );
    draw_vehicle( you, area );
    draw_deck( you, area, s );
    end_frame();
}

auto draw_minimap( avatar &, const catacurses::window &w ) -> void
{
    edge( w );
    wnoutrefresh( w );
    // The pixel minimap is drawn into a window one column inside the sidebar edge, so it never
    // overlaps the rule and edge lines.
    static auto inner = catacurses::window();
    const auto at = point( getbegx( w ) + 1, getbegy( w ) );
    if( !inner || getmaxx( inner ) != getmaxx( w ) - 1 || getmaxy( inner ) != getmaxy( w ) ||
        getbegx( inner ) != at.x || getbegy( inner ) != at.y ) {
        inner = catacurses::newwin( getmaxy( w ), getmaxx( w ) - 1, at );
    }
    werase( inner );
    g->draw_pixel_minimap( inner );
    wnoutrefresh( inner );
}

auto clicked( avatar &you, const point &cell ) -> bool
{
    if( !active() ) {
        return false;
    }
    // Later entries sit on top of earlier ones: the slots over the deck they are drawn in.
    for( auto it = hits.rbegin(); it != hits.rend(); ++it ) {
        const auto &hit = *it;
        const auto &r = hit.at;
        if( cell.x < r.at.x || cell.y < r.at.y || cell.x >= r.at.x + r.width || cell.y >= r.at.y + r.height ) {
            continue;
        }
        if( hit.slot >= 0 ) {
            hotbar::use( you, hit.slot );
        }
        return true;
    }
    return false;
}

auto draw_map_rule( avatar &you, const catacurses::window &w ) -> void
{
    edge( w );
    rule( w, { .title = _( "MAP" ), .summary = current( you ).place } );
    wnoutrefresh( w );
}

auto draw_status( avatar &you, const catacurses::window &w ) -> void
{
    status_section( w, current( you ) );
    wnoutrefresh( w );
}

auto draw_body( avatar &you, const catacurses::window &w ) -> void
{
    edge( w );
    const auto &s = current( you );
    const auto wounded = std::ranges::count_if( s.limbs, []( const auto & l ) { return !l.wound.empty(); } );
    rule( w, {
        .title = _( "BODY" ),
        .summary = wounded > 0 ? string_format( _( "%d wounded" ), wounded ) : std::string( _( "no wounds" ) ),
        .summary_color = wounded > 0 ? pal::danger() : pal::muted()
    } );
    for( auto i = 0; i < static_cast<int>( s.limbs.size() ); ++i ) {
        const auto &limb = s.limbs[static_cast<size_t>( i )];
        const auto hurt = !limb.wound.empty() || limb.hp < limb.hp_max;
        text( w, point( 2, 1 + i ), hurt ? pal::title() : pal::muted(), limb.name );
        bar( w, { .at = point( 9, 1 + i ), .width = 10, .value = limb.hp, .max = limb.hp_max,
                  .fill = limb.wound.empty() ? limb.color : limb.wound_color } );
        text( w, point( 21, 1 + i ), limb.wound_color, limb.wound );
    }
    wnoutrefresh( w );
}

auto draw_around( avatar &you, const catacurses::window &w ) -> void
{
    edge( w );
    const auto &s = current( you );
    const auto hostiles = std::ranges::count_if( s.seen, []( const auto & c ) { return c.hostile; } );
    rule( w, {
        .title = _( "AROUND" ),
        .summary = s.seen.empty() ? std::string( _( "nothing in sight" ) ) :
                   hostiles > 0 ? string_format( _( "%d hostile" ), hostiles ) :
                   string_format( _( "%d in sight" ), static_cast<int>( s.seen.size() ) ),
        .summary_color = hostiles > 0 ? pal::danger() : pal::muted()
    } );
    // Who is there: symbol, name, direction and distance, nearest hostiles first.
    const auto rows = getmaxy( w ) - 1;
    const auto shown = std::min( static_cast<int>( s.seen.size() ), rows );
    const auto room = getmaxx( w ) - 2;
    for( auto i = 0; i < shown; ++i ) {
        const auto &c = s.seen[static_cast<size_t>( i )];
        const auto last = i == rows - 1 && static_cast<int>( s.seen.size() ) > rows;
        if( last ) {
            text( w, point( 2, 1 + i ), pal::muted(),
                  string_format( _( "+%d more" ), static_cast<int>( s.seen.size() ) - i ) );
            break;
        }
        const auto where = c.direction.empty() ? std::string( _( "here" ) ) :
                           string_format( "%s %d", c.direction, c.distance );
        text( w, point( 2, 1 + i ), c.color, c.symbol );
        text( w, point( 4, 1 + i ), c.hostile ? pal::danger() : pal::text(),
              utf8_truncate( c.name, room - 4 - utf8_width( where ) - 2 ) );
        text( w, point( room - utf8_width( where ), 1 + i ), pal::muted(), where );
    }
    wnoutrefresh( w );
}

auto draw_log( avatar &you, const catacurses::window &w ) -> void
{
    edge( w );
    const auto &s = current( you );
    rule( w, { .title = _( "LOG" ) } );
    const auto rows = getmaxy( w ) - 1;
    auto lines = std::vector<std::string>();
    for( const auto &msg : s.log ) {
        const auto folded = foldstring( msg, getmaxx( w ) - 6 );
        for( auto i = size_t{ 0 }; i < folded.size(); ++i ) {
            lines.push_back( ( i == 0 ? std::string( glyph::log ) + " " : std::string( "  " ) ) + folded[i] );
        }
    }
    const auto first = std::max( 0, static_cast<int>( lines.size() ) - rows );
    for( auto i = first; i < static_cast<int>( lines.size() ); ++i ) {
        // Each message keeps the log's own colour: its type while fresh, gray once old.
        text( w, point( 2, 1 + i - first ), pal::text(), lines[static_cast<size_t>( i )] );
    }
    wnoutrefresh( w );
}

} // namespace hud_fusion

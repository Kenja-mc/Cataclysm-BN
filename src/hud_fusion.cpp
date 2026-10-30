#include "hud_fusion.h"

#include <algorithm>
#include <array>
#include <optional>
#include <string>
#include <vector>

#include "action.h"
#include "avatar.h"
#include "catacharset.h"
#include "cursesdef.h"
#include "hud_draw.h"
#include "hotbar.h"
#include "hud_snapshot.h"
#include "input.h"
#include "output.h"
#include "panels.h"
#include "string_formatter.h"
#include "translations.h"

namespace hud_fusion
{

namespace
{

using namespace hud_draw;

constexpr auto status_width = 38;
constexpr auto status_height = 10;
constexpr auto deck_height = 7;

auto need( const catacurses::window &w, const point at, const char *icon, const nc_color icon_color,
           const hud_snapshot::need &n ) -> void
{
    const auto x = text( w, at, icon_color, icon );
    text( w, point( x + 1, at.y ), n.fine ? pal::muted() : n.color,
          n.fine ? std::string( _( "ok" ) ) : n.text );
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

auto draw_status( const canvas &area, const hud_snapshot::snapshot &s ) -> void
{
    const auto w = panel( area, { .at = point_zero, .width = status_width, .height = status_height } );
    card( w, { .title = _( "STATUS" ), .summary = s.stance, .summary_color = s.stance_color } );
    vital( w, { .y = 1, .icon = glyph::hp, .color = s.hp_color, .value = s.hp_percent, .max = 100,
                .label = string_format( "%d%%", s.hp_percent ) } );
    vital( w, { .y = 2, .icon = glyph::stamina, .color = pal::stamina(), .value = s.stamina,
                .max = s.stamina_max, .label = string_format( "%d%%", s.stamina * 100 / s.stamina_max ) } );
    vital( w, { .y = 3, .icon = glyph::focus, .color = pal::focus(), .value = s.focus, .max = 100,
                .label = std::to_string( s.focus ) } );
    text( w, point( 28, 3 ), s.pain_level > 0 ? pal::danger() : pal::muted(),
          string_format( "%s %d", glyph::pain, s.pain_level ) );
    hline( w, point( 2, 4 ), status_width - 4, pal::border() );
    need( w, point( 2, 5 ), glyph::thirst, pal::thirst(), s.thirst );
    need( w, point( 20, 5 ), glyph::rest, pal::rest(), s.rest );
    need( w, point( 2, 6 ), glyph::hunger, pal::hunger(), s.hunger );
    need( w, point( 20, 6 ), glyph::heat, pal::heat(), s.heat );
    auto x = text( w, point( 2, 7 ), s.weight_color, string_format( "%.1f kg", s.weight_kg ) );
    x = dot( w, point( x, 7 ) );
    text( w, point( x, 7 ), s.volume_color, string_format( "%.1f L", s.volume_l ) );
    text( w, point( 2, 8 ), pal::muted(), string_format( "Str %d  Dex %d  Int %d  Per %d", s.str, s.dex, s.intel, s.per ) );
}

auto draw_ribbon( const canvas &area, const hud_snapshot::snapshot &s ) -> void
{
    const auto w = panel( area, {
        .at = point( status_width + 1, 0 ), .width = area.width - status_width - 1, .height = 1
    } );
    auto x = text( w, point( 1, 0 ), pal::title(), s.date + " " + s.time );
    x = dot( w, point( x, 0 ) );
    x = text( w, point( x, 0 ), s.weather_color, s.weather );
    x = dot( w, point( x, 0 ) );
    x = text( w, point( x, 0 ), s.light_color, s.light );
    x = dot( w, point( x, 0 ) );
    x = text( w, point( x, 0 ), s.wind_color, s.wind );
    x = dot( w, point( x, 0 ) );
    x = text( w, point( x, 0 ), pal::muted(), string_format( _( "speed %d  sound %s  mood %d" ), s.speed, s.sound, s.morale ) );
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

auto draw_deck( const avatar &you, const canvas &area, const hud_snapshot::snapshot &s ) -> void
{
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
    for( auto i = 0; i < hotbar::slots; ++i ) {
        const auto v = hotbar::view( you, i );
        const auto sx = slot_x + i * box_w;
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

} // namespace

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
    begin_frame();
    draw_status( area, s );
    draw_ribbon( area, s );
    draw_deck( you, area, s );
    end_frame();
}

auto draw_map_rule( avatar &you, const catacurses::window &w ) -> void
{
    edge( w );
    rule( w, { .title = _( "MAP" ), .summary = current( you ).place } );
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
    // Snapshot order is N, NE, E, SE, S, SW, W, NW, near; the grid reads row by row.
    struct cell {
        const char *label;
        size_t index;
    };
    static constexpr auto grid = std::array<cell, 9> { {
            { "NW", 7 }, { "N", 0 }, { "NE", 1 }, { "W", 6 }, { "@", 8 }, { "E", 2 },
            { "SW", 5 }, { "S", 4 }, { "SE", 3 }
        }
    };
    auto seen = 0;
    for( const auto &c : s.compass ) {
        seen += c.count;
    }
    rule( w, {
        .title = _( "AROUND" ),
        .summary = seen > 0 ? string_format( _( "%d seen" ), seen ) : std::string( _( "clear" ) ),
        .summary_color = seen > 0 ? pal::danger() : pal::muted()
    } );
    const auto column = ( getmaxx( w ) - 4 ) / 3;
    for( auto i = size_t{ 0 }; i < grid.size(); ++i ) {
        const auto &c = s.compass[grid[i].index];
        const auto at = point( 2 + static_cast<int>( i % 3 ) * column, 1 + static_cast<int>( i / 3 ) );
        const auto color = c.count == 0 ? pal::muted() : c.dangerous ? pal::danger() : pal::title();
        const auto x = text( w, at, grid[i].index == 8 ? pal::title() : color, grid[i].label );
        if( c.count > 0 ) {
            text( w, point( x + 1, at.y ), color, string_format( "%s%d", c.symbols, c.count ) );
        }
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
        // Older lines fade so the newest reads first.
        const auto newest = i >= static_cast<int>( lines.size() ) - 2;
        text( w, point( 2, 1 + i - first ), newest ? pal::title() : pal::text(), lines[static_cast<size_t>( i )] );
    }
    wnoutrefresh( w );
}

} // namespace hud_fusion

#include "hud_fusion.h"

#include <algorithm>
#include <array>
#include <optional>
#include <ranges>
#include <string>
#include <utility>
#include <vector>

#include "action.h"
#include "armor_layers.h"
#include "avatar.h"
#include "bodypart.h"
#include "cached_options.h"
#include "catacharset.h"
#include "cursesdef.h"
#include "driving_dashboard.h"
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

/// Icon, the need's name and its state; an unmet need replaces "ok" with its own wording.
struct hit_area {
    rect at;
    /// Hotbar slot index, or -1 for an overlay that only swallows the click.
    int slot = -1;
};
/// Where the last frame drew its overlays, in map-window cells, for click handling.
auto hits = std::vector<hit_area>();
/// Where the LOADOUT section drew its hotbar cells, in sidebar cells, for click handling.
auto loadout_hits = std::vector<hit_area>();
/// Where the STATUS needs line drew the encumbrance entries, in screen cells.
auto encumbered_hits = std::vector<hit_area>();

auto edge( const catacurses::window &w ) -> void;

auto need( const catacurses::window &w, const point at, const char *icon, const nc_color icon_color,
           const hud_snapshot::need &n ) -> int
{
    auto x = text( w, at, icon_color, icon );
    if( n.fine ) {
        x = text( w, point( x + 1, at.y ), pal::muted(), n.label + " " );
        return text( w, point( x, at.y ), pal::muted(), _( "ok" ) );
    }
    return text( w, point( x + 1, at.y ), n.color, n.text );
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

/// The first key bound to `id` on the map, empty when unbound.
auto key_id( const std::string &id ) -> std::string
{
    const auto ctxt = input_context( "DEFAULTMODE" );
    if( ctxt.key_bound_to( id, 0, false ).empty() ) {
        return {};
    }
    const auto desc = ctxt.get_desc( id, 1 );
    return desc == inp_mngr.get_keyname( ' ', input_event_t::keyboard ) ? std::string( _( "spc" ) ) : desc;
}

auto key_for( const action_id act ) -> std::string
{
    return key_id( action_ident( act ) );
}

struct key_entry {
    std::string keys;
    std::string label;
};

/// The keys the current situation needs, centred on one row along the bottom of the map: combat
/// keys while a hostile is in sight, the everyday ones otherwise.
auto draw_keys( const canvas &area, const hud_snapshot::snapshot &s ) -> void
{
    const auto modern = get_option<std::string>( "CONTROL_SCHEME" ) == "modern";
    const auto hostile = std::ranges::any_of( s.seen, []( const auto & c ) {
        return c.hostile;
    } );
    const auto joined = []( const auto & acts ) {
        auto keys = std::string();
        for( const auto act : acts ) {
            keys += key_for( act );
        }
        return keys;
    };
    static const auto moves = std::array{
        ACTION_MOVE_FORTH, ACTION_MOVE_LEFT, ACTION_MOVE_BACK, ACTION_MOVE_RIGHT
    };
    auto entries = std::array<key_entry, 5> {};
    auto count = 0;
    const auto add = [&]( std::string keys, const char *label ) {
        if( !keys.empty() ) {
            entries[static_cast<size_t>( count++ )] = { std::move( keys ), _( label ) };
        }
    };
    if( hostile ) {
        add( key_for( ACTION_FIRE ), modern ? _( "attack" ) : _( "fire" ) );
        add( key_for( ACTION_RELOAD_ITEM ), _( "reload" ) );
        add( key_id( "NEXT_TARGET" ), _( "next target" ) );
        add( key_for( ACTION_OPEN_MOVEMENT ), _( "run" ) );
    } else {
        add( joined( moves ), _( "move" ) );
        add( key_for( ACTION_EXAMINE ), _( "interact" ) );
        add( key_for( ACTION_INVENTORY ), _( "inventory" ) );
        add( key_for( ACTION_ACTIONMENU ), _( "menus" ) );
    }
    add( key_for( ACTION_KEYBINDINGS ), _( "all keys" ) );
    if( count == 0 ) {
        return;
    }
    auto total = 3 * ( count - 1 );
    for( auto i = 0; i < count; ++i ) {
        total += width( entries[static_cast<size_t>( i )].keys ) + 1 +
                 utf8_width( entries[static_cast<size_t>( i )].label );
    }
    hits.push_back( { .at = { .at = point( 0, area.height - 1 ), .width = area.width, .height = 1 } } );
    const auto w = panel( area, { .at = point( 0, area.height - 1 ), .width = area.width, .height = 1 } );
    auto x = std::max( 1, ( area.width - total ) / 2 );
    for( auto i = 0; i < count; ++i ) {
        const auto &e = entries[static_cast<size_t>( i )];
        x = text( w, point( x, 0 ), pal::heading(), e.keys );
        x = text( w, point( x + 1, 0 ), pal::muted(), e.label ) + 3;
    }
}

auto vehicle_card( const canvas &area, const int rows,
                   std::string summary = {} ) -> catacurses::window
{
    const auto height = rows + 2;
    // One row up from the bottom edge, so the key bar keeps the last row of the map.
    const auto at = point( 0, area.height - height - 1 );
    hits.push_back( { .at = { .at = at, .width = 32, .height = height } } );
    auto w = panel( area, {
        .at = at, .width = 32, .height = height
    } );
    card( w, { .title = _( "VEHICLE" ), .summary = std::move( summary ),
               .summary_color = pal::accent() } );
    return w;
}

auto draw_vehicle( const avatar &you, const canvas &area ) -> void
{
    if( get_option<bool>( "DRIVING_DASHBOARD" ) ) {
        auto dash = driving_dashboard::read( you );
        if( !dash.applicable ) {
            return;
        }
        const auto w = vehicle_card( area, static_cast<int>( dash.body.size() ),
                                    std::move( dash.summary ) );
        auto y = 1;
        for( const auto &row : dash.body ) {
            if( !row.icon.empty() ) {
                text( w, point( 2, y ), row.icon_color, row.icon );
            }
            text( w, point( 2 + dash.icon_width, y ), row.text_color, row.text );
            ++y;
        }
        return;
    }
    const auto rows = hud_boxes::vehicle_rows( you );
    if( rows.empty() ) {
        return;
    }
    const auto w = vehicle_card( area, static_cast<int>( rows.size() ) );
    for( auto i = 0; i < static_cast<int>( rows.size() ); ++i ) {
        text( w, point( 2, 1 + i ), rows[static_cast<size_t>( i )].color, rows[static_cast<size_t>( i )].text );
    }
}

/// The LOADOUT section: the held weapon and the hotbar, in the column.
auto loadout_section( const catacurses::window &w, const avatar &you, const hud_snapshot::snapshot &s ) -> void
{
    edge( w );
    rule( w, { .title = _( "LOADOUT" ),
               .summary = string_format( "%s kg  %s L", s.weight, s.volume ),
               .summary_color = pal::muted() } );

    // The held weapon: its map symbol, its name, and the ammo it fires.
    text( w, point( 2, 1 ), s.weapon_color, s.weapon_symbol );
    auto x = text( w, point( 4, 1 ), pal::title(), utf8_truncate( s.weapon, 24 ) );
    if( s.gun ) {
        x = text( w, point( x + 1, 1 ), pal::accent(), s.ammo );
    }
    if( s.armed ) {
        text( w, point( x + 1, 1 ), pal::text(), glyph::weapon );
    }

    // Hotbar: three cells per row, the digit that uses the slot first. Empty slots still draw, so
    // the row shows what there is to fill and where.
    constexpr auto cell_w = 14;
    for( auto i = 0; i < hotbar::slots; ++i ) {
        const auto v = hotbar::view( you, i );
        const auto sx = 2 + ( i % 3 ) * cell_w;
        const auto sy = 2 + i / 3;
        loadout_hits.push_back( { .at = { .at = point( getbegx( w ) + sx, getbegy( w ) + sy ),
                                         .width = cell_w, .height = 1 }, .slot = i } );
        const auto ready = v.assigned && v.count > 0;
        auto cx = text( w, point( sx, sy ), v.wielded ? pal::accent() : pal::heading(), std::to_string( i + 1 ) );
        if( !v.assigned ) {
            text( w, point( cx + 1, sy ), pal::border(), "·" );
            continue;
        }
        cx = text( w, point( cx + 1, sy ), ready ? v.color : pal::border(), " " + v.symbol );
        const auto label = v.name + ( v.count > 1 ? " x" + std::to_string( v.count ) : std::string() );
        text( w, point( cx + 1, sy ), ready ? pal::title() : pal::muted(), utf8_truncate( label, cell_w - 6 ) );
    }
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

/// The body panel's wound wording, with the first letter up so it heads a row.
auto sentence( std::string text ) -> std::string
{
    if( !text.empty() && text.front() >= 'a' && text.front() <= 'z' ) {
        text.front() = static_cast<char>( text.front() - 'a' + 'A' );
    }
    return text;
}

/// The needs line: one row that only names what needs action, and says so when nothing does.
auto needs_line( const catacurses::window &w, const hud_snapshot::snapshot &s ) -> void
{
    constexpr auto y = 4;
    struct chip {
        const hud_snapshot::need *reading;
        const char *icon;
        nc_color icon_color;
    };
    const auto chips = std::array{
        chip{ .reading = &s.thirst, .icon = glyph::thirst, .icon_color = pal::thirst() },
        chip{ .reading = &s.hunger, .icon = glyph::hunger, .icon_color = pal::hunger() },
        chip{ .reading = &s.rest, .icon = glyph::rest, .icon_color = pal::rest() },
        chip{ .reading = &s.heat, .icon = glyph::heat, .icon_color = pal::heat() },
    };
    auto x = 2;
    const auto all_fine = std::ranges::all_of( chips, []( const auto & c ) {
        return c.reading->fine;
    } );
    const auto wounded = std::ranges::any_of( s.limbs, []( const auto & l ) {
        return !l.wound.empty();
    } );
    if( s.pain_level == 0 && all_fine && !wounded && s.encumbered.empty() ) {
        x = text( w, point( x, y ), pal::muted(),
                  std::string( glyph::check ) + " " + _( "Needs met" ) ) + 2;
        x = text( w, point( x, y ), pal::muted(), string_format( _( "Focus %d" ), s.focus ) );
        x = dot( w, point( x, y ) );
        text( w, point( x, y ), s.morale < -10 ? pal::danger() :
              s.morale > 10 ? c_light_green : pal::muted(),
              string_format( _( "Mood %+d" ), s.morale ) );
        return;
    }
    for( const auto &c : chips ) {
        if( !c.reading->fine ) {
            x = need( w, point( x, y ), c.icon, c.icon_color, *c.reading ) + 2;
        }
    }
    if( s.pain_level > 0 ) {
        x = text( w, point( x, y ), s.pain.color, string_format( _( "Pain %d" ), s.pain_level ) ) + 2;
    }
    // Each wound is named with the limb that carries it, in the wound's own colour, so a bleeding
    // arm cannot hide behind a calm needs row.
    for( const auto &limb : s.limbs ) {
        if( limb.wound.empty() ) {
            continue;
        }
        x = text( w, point( x, y ), limb.wound_color, sentence( limb.wound ) );
        x = text( w, point( x + 1, y ), pal::text(), limb.name ) + 2;
    }
    // The worst encumbered parts come first, in the colour the character sheet gives them; a long
    // list folds into a count so the row never pushes the log off the section.
    if( s.encumbered.empty() ) {
        return;
    }
    constexpr auto named = 2;
    const auto start = x;
    for( auto i = 0; i < static_cast<int>( s.encumbered.size() ) && i < named; ++i ) {
        const auto &e = s.encumbered[static_cast<size_t>( i )];
        x = text( w, point( x, y ), e.color, string_format( _( "Encumbered %s" ), e.name ) ) + 2;
    }
    if( static_cast<int>( s.encumbered.size() ) > named ) {
        x = text( w, point( x, y ), s.encumbered[static_cast<size_t>( named )].color,
                  string_format( "+%d", static_cast<int>( s.encumbered.size() ) - named ) );
    }
    encumbered_hits.push_back( { .at = { .at = point( getbegx( w ) + start, getbegy( w ) + y ),
                                        .width = std::max( 1, x - start ), .height = 1 } } );
}

/// The STATUS section: the original BN limb grid, Stamina, and the needs that need action. It sits
/// in the column so nothing covers the map.
auto status_section( const catacurses::window &w, const avatar &you, const hud_snapshot::snapshot &s ) -> void
{
    edge( w );
    rule( w, { .title = _( "STATUS" ), .summary = s.stance, .summary_color = s.stance_color } );
    // Two rows of three, the limbs laid out as they sit on the body: every limb keeps its own bar
    // and the limbs panel's colours, so the one that was hit stands out.
    constexpr auto column_step = 14;
    static const auto grid = std::array{
        bodypart_str_id( "arm_l" ), bodypart_str_id( "head" ), bodypart_str_id( "arm_r" ),
        bodypart_str_id( "leg_l" ), bodypart_str_id( "torso" ), bodypart_str_id( "leg_r" ),
    };
    for( auto i = 0; i < static_cast<int>( grid.size() ); ++i ) {
        const auto &bp = grid[static_cast<size_t>( i )];
        const auto at = point( 2 + ( i % 3 ) * column_step, 1 + i / 3 );
        auto x = text( w, at, you.limb_color( bp, true, true, true ), body_part_hp_bar_ui_text( bp ) );
        const auto hp = limb_health_text( you, bp );
        x = text( w, point( x + 1, at.y ), hp.color, hp.text );
        if( hp.pad > 0 ) {
            text( w, point( x, at.y ), c_white, std::string( static_cast<size_t>( hp.pad ), '.' ) );
        }
    }
    const auto stamina = s.stamina_max > 0 ? s.stamina * 100 / s.stamina_max : 0;
    vital( w, { .y = 3, .icon = glyph::stamina, .color = pal::stamina(), .value = s.stamina,
                .max = s.stamina_max, .label = string_format( _( "Stamina %d%%" ), stamina ) } );
    // Walking is the normal reading, so only a slowed turn is worth the cells.
    if( s.speed != 100 ) {
        text( w, point( 34, 3 ), pal::muted(), string_format( _( "Speed %d" ), s.speed ) );
    }
    needs_line( w, s );
}

} // namespace

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
    // The minimap gives way first, so every section below it still fits on the screen.
    const auto rest = 1 + status_rows + loadout_rows +
                      around_rows( get_avatar() ) + sidebar::log_min_rows;
    return std::clamp( chosen > 0 ? chosen : 12, 6, std::max( 6, TERMY - rest ) );
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
    loadout_hits.clear();
    encumbered_hits.clear();
    begin_frame();
    draw_ribbon( area, s );
    draw_keys( area, s );
    draw_vehicle( you, area );
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
    // The hotbar lives in the column now: a click there uses a slot, a click on the encumbrance
    // entries opens the armor screen, and any other click on the column stops here instead of
    // reaching the map behind it.
    if( get_option<std::string>( "SIDEBAR_POSITION" ) == "right" ) {
        const auto sidebar_x = TERMX - panel_manager::get_manager().get_width_right();
        if( cell.x >= sidebar_x ) {
            for( const auto &hit : encumbered_hits ) {
                const auto &r = hit.at;
                if( cell.x >= r.at.x && cell.x < r.at.x + r.width && cell.y >= r.at.y &&
                    cell.y < r.at.y + r.height ) {
                    show_armor_layers_ui( you );
                    return true;
                }
            }
            for( const auto &hit : loadout_hits ) {
                const auto &r = hit.at;
                if( cell.x >= r.at.x && cell.x < r.at.x + r.width && cell.y >= r.at.y &&
                    cell.y < r.at.y + r.height ) {
                    hotbar::use( you, hit.slot );
                    return true;
                }
            }
            return true;
        }
    }
    // Later entries sit on top of earlier ones: the vehicle card over the map it sits on.
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
    status_section( w, you, current( you ) );
    wnoutrefresh( w );
}

auto draw_loadout( avatar &you, const catacurses::window &w ) -> void
{
    loadout_section( w, you, current( you ) );
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

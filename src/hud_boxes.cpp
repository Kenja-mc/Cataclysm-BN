#include "hud_boxes.h"
#include "hud_sidebar.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <cstdint>
#include <optional>
#if !defined(TILES) && !defined(_WIN32)
#include <langinfo.h>
#endif
#include <string>
#include <utility>
#include <vector>

#include "avatar.h"
#include "bodypart.h"
#include "calendar.h"
#include "catacharset.h"
#include "cata_utility.h"
#include "character_functions.h"
#include "character_martial_arts.h"
#include "color.h"
#include "cursesdef.h"
#include "effect.h"
#include "flag.h"
#include "game.h"
#include "hud_windows.h"
#include "icon_font.h"
#include "item.h"
#include "magic/magic.h"
#include "messages.h"
#include "mtype.h"
#include "needs_status.h"
#include "options.h"
#include "output.h"
#include "overmap/overmapbuffer_registry.h"
#include "panels.h"
#include "panels_utility.h"
#include "sounds.h"
#include "string_formatter.h"
#include "translations.h"
#include "units.h"
#include "weather/weather.h"
#include "units_utility.h"
#include "vehicle/vehicle.h"
#include "vehicle/vehicle_part.h"

namespace
{

/// Whether the terminal can show Unicode box drawing; tiles builds always can.
auto unicode_locale() -> bool
{
#if defined(TILES) || defined(_WIN32)
    return true;
#else
    // The code set is fixed once the game has set its locale.
    static const auto utf8 = std::strcmp( nl_langinfo( CODESET ), "UTF-8" ) == 0;
    return utf8;
#endif
}

struct frame_glyphs {
    const char *horizontal;
    const char *vertical;
    const char *top_left;
    const char *top_right;
    const char *bottom_left;
    const char *bottom_right;
};

auto frame_for( const bool unicode, const bool rounded ) -> frame_glyphs
{
    if( !unicode ) {
    return { .horizontal = "-", .vertical = "|", .top_left = "+", .top_right = "+", .bottom_left = "+", .bottom_right = "+" };
}
if( rounded ) {
    return { .horizontal = "─", .vertical = "│", .top_left = "╭", .top_right = "╮", .bottom_left = "╰", .bottom_right = "╯" };
}
return { .horizontal = "─", .vertical = "│", .top_left = "┌", .top_right = "┐", .bottom_left = "└", .bottom_right = "┘" };
}

/// Scanned every draw: a per-turn cache went stale when the avatar picked a thermometer up.
auto has_thermometer( const avatar &you ) -> bool
{
    return you.has_item_with_flag( flag_THERMOMETER ) ||
    you.has_enchantment_flag( enchantment_flag_id( "THERMOMETER" ) );
}

/// One-row corner bars leave the sidebar panels in place instead of replacing them.
auto compact_bars() -> bool
{
    return !hud_sidebar::active() && get_option<bool>( "HUD_CORNER_BARS" );
}

enum class icon {
    sun, moon, cloud, rain, storm, snow, strange, underground, fists, melee, gun, bow, style,
    walk, run, crouch, prone, mana, compass, fuel, battery, pain, thirst, hunger, rest, temp,
    cold, hot, clock, light, wind, needs_met
};

struct glyph_set {
    const char *uni;
    /// Material Design Icons codepoint, as a terminal Nerd Font provides it.
    const char *mdi;
    /// The bundled font's two-cell copy, drawn by builds that load it.
    const char *bundled;
    const char *ascii;
};

/// One glyph per icon for each icon set.
auto glyph( const icon i, const std::string &style ) -> std::string
{
    const auto pick = [&]( const glyph_set & g ) {
        if( style == "ascii" ) {
            return std::string( g.ascii );
        }
        if( style == "nerd" ) {
            return std::string( icon_font::bundled ? g.bundled : g.mdi );
        }
        return std::string( g.uni );
    };
    // Stance figures are people, which no Unicode symbol shows; builds with the bundled font
    // draw them in every icon set but text.
    const auto stance = [&]( const char *figure, const char *uni, const char *ascii ) {
        return style == "ascii" ? std::string( ascii ) :
               icon_font::bundled ? std::string( figure ) : std::string( uni );
    };
    switch( i ) {
        case icon::sun:
            return pick( { .uni = "☼", .mdi = "\U000F0599", .bundled = icon_font::weather_sunny, .ascii = "*" } );
        case icon::moon:
            return pick( { .uni = "☾", .mdi = "\U000F0594", .bundled = icon_font::weather_night, .ascii = "C" } );
        case icon::cloud:
            return pick( { .uni = "☁", .mdi = "\U000F0590", .bundled = icon_font::weather_cloudy, .ascii = "~" } );
        case icon::rain:
            return pick( { .uni = "☂", .mdi = "\U000F0597", .bundled = icon_font::weather_rainy, .ascii = "/" } );
        case icon::storm:
            return pick( { .uni = "↯", .mdi = "\U000F0593", .bundled = icon_font::weather_lightning, .ascii = "!" } );
        case icon::snow:
            return pick( { .uni = "❄", .mdi = "\U000F0598", .bundled = icon_font::weather_snowy, .ascii = "*" } );
        case icon::strange:
            return pick( { .uni = "◎", .mdi = "\U000F0591", .bundled = icon_font::weather_fog, .ascii = "%" } );
        case icon::underground:
            return pick( { .uni = "▼", .mdi = "\U000F12BE", .bundled = icon_font::stairs_down, .ascii = "v" } );
        case icon::fists:
            return pick( { .uni = "✶", .mdi = "\U000F0B65", .bundled = icon_font::boxing_glove, .ascii = "f" } );
        case icon::melee:
            return pick( { .uni = "⚔", .mdi = "\U000F04E5", .bundled = icon_font::sword, .ascii = "/" } );
        case icon::gun:
            return pick( { .uni = "⌖", .mdi = "\U000F0703", .bundled = icon_font::pistol, .ascii = "=" } );
        case icon::bow:
            return pick( { .uni = "➶", .mdi = "\U000F1841", .bundled = icon_font::bow_arrow, .ascii = ")" } );
        case icon::style:
            return pick( { .uni = "☯", .mdi = "\U000F082C", .bundled = icon_font::karate, .ascii = "*" } );
        case icon::walk:
            return stance( icon_font::walk, "•", "." );
        case icon::run:
            return stance( icon_font::run, "▶", ">" );
        case icon::crouch:
            return stance( icon_font::crouch, "▼", "v" );
        case icon::prone:
            return stance( icon_font::prone, "━", "-" );
        case icon::mana:
            return pick( { .uni = "✦", .mdi = "\U000F0AE2", .bundled = icon_font::star_four_points, .ascii = "+" } );
        case icon::compass:
            return pick( { .uni = "⊕", .mdi = "\U000F018B", .bundled = icon_font::compass, .ascii = "+" } );
        case icon::fuel:
            return pick( { .uni = "▤", .mdi = "\U000F0298", .bundled = icon_font::gas_station, .ascii = "F" } );
        case icon::battery:
            return pick( { .uni = "↯", .mdi = "\U000F0079", .bundled = icon_font::battery, .ascii = "B" } );
        case icon::pain:
            return pick( { .uni = "☹", .mdi = "\U000F0DAF", .bundled = icon_font::bandage, .ascii = "x" } );
        case icon::thirst:
            return pick( { .uni = "☕", .mdi = "\U000F01AB", .bundled = icon_font::cup_water, .ascii = "~" } );
        case icon::hunger:
            return pick( { .uni = "♨", .mdi = "\U000F141F", .bundled = icon_font::food_drumstick, .ascii = "@" } );
        case icon::rest:
            return pick( { .uni = "z", .mdi = "\U000F0904", .bundled = icon_font::power_sleep, .ascii = "z" } );
        case icon::temp:
            return pick( { .uni = "⇅", .mdi = "\U000F050F", .bundled = icon_font::thermometer, .ascii = "=" } );
        case icon::cold:
            return pick( { .uni = "❄", .mdi = "\U000F0598", .bundled = icon_font::weather_snowy, .ascii = "*" } );
        case icon::hot:
            return pick( { .uni = "↑", .mdi = "\U000F050F", .bundled = icon_font::thermometer, .ascii = "^" } );
        case icon::clock:
            return pick( { .uni = "◷", .mdi = "\U000F0150", .bundled = icon_font::clock_outline, .ascii = "t" } );
        case icon::light:
            return pick( { .uni = "⊙", .mdi = "\U000F06E8", .bundled = icon_font::lightbulb_on, .ascii = "l" } );
        case icon::wind:
            return pick( { .uni = "≈", .mdi = "\U000F059D", .bundled = icon_font::weather_windy, .ascii = "w" } );
        case icon::needs_met:
            return pick( { .uni = "✓", .mdi = "\U000F012C", .bundled = icon_font::check, .ascii = "+" } );
    }
    return "?";
}

auto weather_icon( const std::string &id ) -> icon
{
    const auto has = [&]( const char *part ) {
        return id.find( part ) != std::string::npos;
    };
    if( has( "portal" ) ) {
        return icon::strange;
    }
    if( has( "snow" ) || has( "flurr" ) ) {
        return icon::snow;
    }
    if( has( "thunder" ) || has( "lightning" ) || has( "storm" ) ) {
        return icon::storm;
    }
    if( has( "rain" ) || has( "drizzle" ) ) {
        return icon::rain;
    }
    if( has( "cloud" ) || has( "fog" ) ) {
        return icon::cloud;
    }
    return is_night( calendar::turn ) ? icon::moon : icon::sun;
}

struct line {
    std::string icon;
    int icon_w;
    nc_color icon_color;
    std::string text;
    nc_color text_color;
    std::string label;
};

auto time_text( const avatar &you ) -> std::string
{
    if( you.has_watch() ) {
    return to_string_time_of_day( calendar::turn );
    }
    if( you.bub_pos().z() < 0 ) {
    return _( "???" );
    }
    const auto hour = hour_of_day<int>( calendar::turn );
    return hour < 5 ? _( "night" ) : hour < 8 ? _( "dawn" ) : hour < 12 ? _( "morning" ) :
           hour < 14 ? _( "noon" ) : hour < 18 ? _( "afternoon" ) : hour < 21 ? _( "evening" ) : _( "night" );
}

auto season_day_text() -> std::string
{
    //~ Season and day, e.g. "Spring 21".
    return string_format( _( "%s %d" ),
    calendar::name_season( season_of_year( calendar::turn ) ),
    day_of_season<int>( calendar::turn ) + 1 );
}

/// The visible body for each moon phase, in `moon_phase` order.
auto moon_glyph( const moon_phase phase, const std::string &style ) -> std::string
{
    constexpr auto uni = std::array{ "○", "☽", "◑", "◕", "●", "◕", "◐", "☾" };
    constexpr auto mdi = std::array{
        "\U000F0F64", "\U000F0F67", "\U000F0F61", "\U000F0F68",
        "\U000F0F62", "\U000F0F66", "\U000F0F63", "\U000F0F65"
    };
    constexpr auto bundled = std::array{
        icon_font::moon_new, icon_font::moon_waxing_crescent, icon_font::moon_first_quarter,
        icon_font::moon_waxing_gibbous, icon_font::moon_full, icon_font::moon_waning_gibbous,
        icon_font::moon_last_quarter, icon_font::moon_waning_crescent
    };
    constexpr auto ascii = std::array{ "o", ")", "]", "D", "O", "C", "[", "(" };
    const auto index = static_cast<size_t>( phase ) % uni.size();
    if( style == "nerd" ) {
        return icon_font::bundled ? bundled[index] : mdi[index];
    }
    return style == "ascii" ? ascii[index] : uni[index];
}

/// A short arc of the sky with the sun, or the moon in its current phase, at its place in its
/// day or night; the moon is drawn in its phase so the night's light can be judged at a glance.
auto sky_track( const std::string &style ) -> std::string
{
    constexpr auto cells = 9;
    constexpr auto day_minutes = 24 * 60;
    const auto now = to_minutes<int>( time_past_midnight( calendar::turn ) );
    const auto rise = to_minutes<int>( time_past_midnight( sunrise( calendar::turn ) ) );
    const auto set = to_minutes<int>( time_past_midnight( sunset( calendar::turn ) ) );
    const auto daytime = now >= rise && now < set;
    // Permanent day or night dimensions override the clock.
    const auto sun = is_night( calendar::turn ) ? false : is_day( calendar::turn ) ? true : daytime;
    auto fraction = 0.5;
    if( sun && daytime && set > rise ) {
        fraction = static_cast<double>( now - rise ) / ( set - rise );
    } else if( !sun && !daytime && set > rise ) {
        const auto into = now >= set ? now - set : now + day_minutes - set;
        fraction = static_cast<double>( into ) / ( day_minutes - ( set - rise ) );
    }
    const auto slot = std::clamp( static_cast<int>( std::lround( fraction * ( cells - 1 ) ) ), 0,
                                  cells - 1 );
    const auto phase = get_moon_phase( calendar::turn );
    const auto body = sun ? colorize( glyph( icon::sun, style ), c_yellow ) :
                      colorize( moon_glyph( phase, style ), phase == MOON_NEW ? c_dark_gray : c_white );
    const auto dot = std::string( style == "ascii" ? "-" : "·" );
    auto track = std::string();
    for( auto cell = 0; cell < cells; ++cell ) {
        track += cell == slot ? body : dot;
    }
    return track;
}

struct wind_info {
    std::string text;
    nc_color color;
};

/// Local wind as the Wind panel shows it: description plus arrow, colored by strength.
auto wind_text( const avatar &you, const bool ascii ) -> wind_info
{
    const oter_id &cur_om_ter = ACTIVE_OVERMAP_BUFFER.ter( you.abs_omt_pos() );
    const weather_manager &weather = get_weather();
    const double windpower = get_local_windpower( weather.windspeed, cur_om_ter,
        you.abs_pos(), weather.winddirection,
        weather::is_sheltered( get_map(), you.bub_pos() ) );
    auto direction = get_wind_arrow( weather.winddirection );
    if( ascii ) {
        constexpr auto arrows = std::array{ "⇓", "⇙", "⇐", "⇖", "⇑", "⇗", "⇒", "⇘" };
        const auto found = std::ranges::find( arrows, direction );
        if( found != arrows.end() ) {
            // Arrows show flow; letters name the origin.
            constexpr auto names = std::array{ "N", "NE", "E", "SE", "S", "SW", "W", "NW" };
            direction = names[static_cast<size_t>( found - arrows.begin() )];
        }
    }
    return { .text = get_wind_desc( windpower ) + " " + direction,
             .color = get_wind_color( windpower ) };
}

/// Weather row text: the condition, plus the temperature when the avatar carries a thermometer.
auto weather_text( const avatar &you, const bool underground ) -> std::string
{
    const auto &w = get_weather();
    auto text = underground ? std::string( _( "Underground" ) ) : w.weather_id->name.translated();
    if( has_thermometer( you ) ) {
        text += "  " + print_temperature( w.get_temperature( you.abs_pos() ) );
    }
    return text;
}

auto weather_lines( const avatar &you, const std::string &icons ) -> std::vector<line>
{
    auto out = std::vector<line>();
    out.reserve( 4 );
    const auto &w = get_weather();
    const auto underground = you.bub_pos().z() < 0;
    const auto first = icons == "ascii" ? std::string() :
                       underground ? glyph( icon::underground, icons ) :
                       glyph( weather_icon( w.weather_id.str() ), icons );
    const auto description = weather_text( you, underground );
    // Underground the sky cannot be seen.
    const auto date = season_day_text() + " " + time_text( you ) +
                      ( underground ? std::string() : "  " + sky_track( icons ) );
    if( compact_bars() ) {
        const auto light = get_light_level( character_funcs::fine_detail_vision_mod( you ) );
        const auto wind = wind_text( you, icons == "ascii" );
        const auto label = icons == "ascii" ? std::string( _( "Weather" ) ) + ": " + description :
                           description;
        auto text = label;
        text += "  │  " + date;
        text += "  │  " + string_format( _( "Light: %s" ), light.first );
        text += "  │  " + string_format( _( "Wind: %s" ), wind.text );
        return { {
                .icon = first, .icon_w = utf8_width( first ),
                .icon_color = underground ? c_light_gray : w.weather_id->color,
                .text = text,
                .text_color = underground ? c_light_gray : w.weather_id->color
            } };
    }
    out.push_back( { .icon = first, .icon_w = utf8_width( first ),
                     .icon_color = underground ? c_light_gray : w.weather_id->color,
                     .text = icons == "ascii" ? std::string( _( "Weather" ) ) + ": " + description : description,
                     .text_color = underground ? c_light_gray : w.weather_id->color } );
    const auto clock = glyph( icon::clock, icons );
    out.push_back( { .icon = clock, .icon_w = utf8_width( clock ), .icon_color = c_light_gray,
                     .text = date, .text_color = c_light_gray } );
    const auto light = get_light_level( character_funcs::fine_detail_vision_mod( you ) );
    const auto light_icon = glyph( icon::light, icons );
    out.push_back( { .icon = light_icon, .icon_w = utf8_width( light_icon ), .icon_color = light.second,
                     .text = string_format( _( "Light: %s" ), light.first ), .text_color = light.second } );
    const auto wind = wind_text( you, icons == "ascii" );
    const auto wind_icon = glyph( icon::wind, icons );
    out.push_back( { .icon = wind_icon, .icon_w = utf8_width( wind_icon ), .icon_color = wind.color,
                     .text = string_format( _( "Wind: %s" ), wind.text ), .text_color = wind.color } );
    return out;
}

struct need_row {
    icon symbol;
    std::string label;
    needs_status::reading value;
};

/// Only the extremes of the temperature reading reach the summary, so each carries its own icon.
auto temperature_icon( const needs_status::reading &value ) -> icon
{
    if( value.side == needs_status::thermal::cold ) {
        return icon::cold;
    }
    return value.side == needs_status::thermal::hot ? icon::hot : icon::temp;
}

/// Only needs that call for attention; a satisfied need would fill a row with good news.
auto pressing_needs( const avatar &you ) -> std::vector<need_row>
{
    const auto values = needs_status::read( you );
    auto all = std::array{
        need_row{ .symbol = icon::pain, .label = _( "Pain" ), .value = values.pain },
        need_row{ .symbol = icon::thirst, .label = _( "Thirst" ), .value = values.thirst },
        need_row{ .symbol = icon::hunger, .label = _( "Hunger" ), .value = values.hunger },
        need_row{ .symbol = icon::rest, .label = _( "Rest" ), .value = values.rest },
        need_row{
            .symbol = temperature_icon( values.heat ), .label = _( "Body temp" ),
            .value = values.heat }
    };
    return all
    | std::views::filter( []( const need_row & n ) { return !n.value.fine; } )
    | std::ranges::to<std::vector>();
}

auto combat_lines( const avatar &you, const std::string &icons,
                   const bool needs ) -> std::vector<line>
{
    auto out = std::vector<line>();
    out.reserve( 10 );
    const auto &weapon = you.primary_weapon();
    auto kind = icon::fists;
    if( you.is_armed() ) {
        kind = !weapon.is_gun() ? icon::melee :
               weapon.gun_skill() == skill_id( "archery" ) ? icon::bow : icon::gun;
    }
    const auto name = you.is_armed() ? character_funcs::fmt_wielded_weapon( you ) : std::string(
                          _( "fists" ) );
    const auto style = you.martial_arts_data->selected_is_none() ? std::string() :
                       you.martial_arts_data->selected_style_name( you );
    auto stance_icon = icon::walk;
    auto stance_color = c_light_gray;
    auto stance_text = _( "Walking" );
    if( you.movement_mode_is( CMM_RUN ) ) {
        stance_icon = icon::run;
        stance_color = c_red;
        stance_text = _( "Running" );
    } else if( you.movement_mode_is( CMM_CROUCH ) ) {
        stance_icon = icon::crouch;
        stance_color = c_light_blue;
        stance_text = _( "Crouching" );
    } else if( you.movement_mode_is( CMM_PRONE ) ) {
        stance_icon = icon::prone;
        stance_color = c_brown;
        stance_text = _( "Prone" );
    }
    const auto pressing = needs ? pressing_needs( you ) : std::vector<need_row>();
    if( compact_bars() ) {
        auto text = name + ( style.empty() ? std::string() : "  │  " + style ) + "  │  " + stance_text;
        if( needs && pressing.empty() ) {
            text += "  │  " + std::string( _( "Needs met" ) );
        }
        for( const auto &need : pressing ) {
            text += "  │  " + need.label + " " + need.value.text;
        }
        if( hud_boxes::mana_matters( you ) ) {
            text += string_format( _( "  │  Mana %s" ), hud_boxes::mana_reading( you ).text );
        }
        const auto ic = icons == "ascii" ? std::string() : glyph( kind, icons );
        return { {
                .icon = ic, .icon_w = utf8_width( ic ), .icon_color = c_light_cyan,
                .text = text, .text_color = c_light_gray
            } };
    }
    const auto add = [&]( const icon symbol, const nc_color icon_color, const std::string & text,
    const nc_color text_color, const std::string & label ) {
        const auto ic = icons == "ascii" ? std::string() : glyph( symbol, icons );
        out.push_back( { .icon = ic, .icon_w = utf8_width( ic ), .icon_color = icon_color,
                         .text = text, .text_color = text_color, .label = label } );
    };
    add( kind, c_light_cyan, name, c_light_gray, _( "Weapon" ) );
    add( stance_icon, stance_color, stance_text, stance_color, _( "Stance" ) );
    if( !style.empty() ) {
        add( icon::style, c_light_blue, style, c_light_gray, _( "Style" ) );
    }
    if( needs && pressing.empty() ) {
        add( icon::needs_met, c_green, _( "Needs met" ), c_green, _( "Needs" ) );
    }
    for( const auto &need : pressing ) {
        add( need.symbol, need.value.color, need.value.text, need.value.color, need.label );
    }
    if( hud_boxes::mana_matters( you ) ) {
        const auto mana = hud_boxes::mana_reading( you );
        add( icon::mana, mana.color, mana.text, mana.color, _( "Mana" ) );
    }
    return out;
}

/// Columns the one-row weather bar needs, icon column included.
auto weather_bar_width( const avatar &you, const std::string &icons ) -> int
{
    const auto lines = weather_lines( you, icons );
    const auto &line = lines.front();
    return line.icon_w + ( line.icon_w > 0 ? 1 : 0 ) + utf8_width( line.text, true );
}

/// Columns the one-row status bar needs, icon column included.
auto combat_bar_width( const avatar &you, const std::string &icons, bool needs ) -> int
{
    const auto lines = combat_lines( you, icons, needs );
    const auto &line = lines.front();
    return line.icon_w + ( line.icon_w > 0 ? 1 : 0 ) + utf8_width( line.text, true );
}

struct vehicle_state {
    vehicle *veh = nullptr;
    std::optional<itype_id> engine_fuel;
    bool battery = false;
    bool wing = false;
    int rows = 0;
};

auto current_vehicle( const avatar &you ) -> vehicle_state
{
    auto state = vehicle_state{ .veh = g->remoteveh() };
    if( state.veh == nullptr && you.in_vehicle ) {
        state.veh = veh_pointer_or_null( get_map().veh_at( you.bub_pos() ) );
    }
    if( state.veh == nullptr ) {
        return state;
    }
    auto *veh = state.veh;
    static const auto fuel_type_battery = itype_id( "battery" );
    static const auto fuel_type_muscle = itype_id( "muscle" );
    for( auto e = size_t{ 0 }; e < veh->engines.size(); ++e ) {
        if( veh->is_perpetual_type( e ) || veh->is_engine_type( e, fuel_type_muscle ) ) {
            continue;
        }
        const auto &fuel = veh->cpart( veh->engines[e] ).fuel_current();
        if( fuel.is_null() ) {
            continue;
        }
        if( !state.engine_fuel || veh->is_engine_on( e ) ) {
            state.engine_fuel = fuel;
        }
        if( veh->is_engine_on( e ) ) {
            break;
        }
    }
    if( state.engine_fuel == fuel_type_battery ) {
        state.engine_fuel.reset();
    }
    state.battery = veh->fuel_capacity( fuel_type_battery ) > 0;
    state.wing = veh->has_part( "WING" );
    state.rows = 3 + veh->cruise_on + state.wing + state.engine_fuel.has_value() + state.battery;
    return state;
}

auto vehicle_lines( const vehicle_state &state, const std::string &icons ) -> std::vector<line>
{
    auto out = std::vector<line>();
    auto *veh = state.veh;
    if( veh == nullptr ) {
        return out;
    }
    const auto ascii = icons == "ascii";
    out.reserve( state.rows );
    static const auto fuel_type_battery = itype_id( "battery" );
    {
        const auto ic = ascii ? std::string() : glyph( icon::compass, icons );
        const auto iw = utf8_width( ic );
        out.push_back( { .icon = std::move( ic ), .icon_w = iw, .icon_color = c_light_gray,
                         .text = string_format( _( "Azimuth: %s" ), veh->face.to_string_azimuth_from_north() ),
                         .text_color = c_light_gray } );
        const auto indent = std::string( iw, ' ' );
        const auto strain = veh->strain();
        const auto speed_color = strain <= 0 ? c_light_blue :
                                 strain <= 0.2 ? c_yellow : strain <= 0.4 ? c_light_red : c_red;
        out.push_back( { .icon = indent, .icon_w = iw, .icon_color = speed_color,
                         .text = string_format( _( "Speed: %d %s" ),
                                                static_cast<int>( convert_velocity( veh->velocity, VU_VEHICLE ) ),
                                                velocity_units( VU_VEHICLE ) ),
                         .text_color = speed_color } );
        if( veh->cruise_on ) {
            out.push_back( { .icon = indent, .icon_w = iw, .icon_color = c_light_gray,
                             .text = string_format( _( "Cruise: %d %s" ),
                                                    static_cast<int>( convert_velocity( veh->cruise_velocity, VU_VEHICLE ) ),
                                                    velocity_units( VU_VEHICLE ) ),
                             .text_color = c_light_gray } );
        }
        if( state.wing ) {
            const auto takeoff = veh->get_takeoff_speed();
            out.push_back( { .icon = indent, .icon_w = iw, .icon_color = c_light_gray,
                             .text = string_format( _( "Takeoff: %d %s" ),
                                                    takeoff,
                                                    velocity_units( VU_VEHICLE ) ),
                             .text_color = convert_velocity( veh->velocity, VU_VEHICLE ) >= takeoff ?
                                           c_light_green : c_light_red } );
        }
        out.push_back( { .icon = indent, .icon_w = iw, .icon_color = c_light_gray,
                         .text = veh->engine_on ? _( "Engine: on" ) : _( "Engine: off" ),
                         .text_color = veh->engine_on ? c_light_green : c_light_gray } );
    }

    const auto percentage = [&]( const itype_id & fuel ) {
        const auto capacity = veh->fuel_capacity( fuel );
        return capacity > 0 ? static_cast<int>(
                   static_cast<int64_t>( veh->fuel_left( fuel ) ) * 100 / capacity ) : 0;
    };
    if( state.engine_fuel ) {
        const auto percent = percentage( *state.engine_fuel );
        const auto ic = ascii ? std::string() : glyph( icon::fuel, icons );
        const auto iw = utf8_width( ic );
        out.push_back( { .icon = std::move( ic ), .icon_w = iw, .icon_color = c_light_gray,
                         .text = string_format( _( "%s: %d%%" ), item::nname( *state.engine_fuel ), percent ),
                         .text_color = percent > 20 ? c_light_gray : percent > 5 ? c_yellow : c_red } );
    }
    if( state.battery ) {
        const auto percent = percentage( fuel_type_battery );
        const auto color = percent > 20 ? c_light_cyan : percent > 5 ? c_yellow : c_red;
        const auto ic = ascii ? std::string() : glyph( icon::battery, icons );
        const auto iw = utf8_width( ic );
        out.push_back( { .icon = std::move( ic ), .icon_w = iw, .icon_color = color,
                         .text = string_format( _( "Battery: %d%%" ), percent ), .text_color = color } );
    }
    return out;
}

/// Draws the lines in a bordered box whose top-left corner is `at`.
struct box_spec {
    point at;
    int inner = 0;
    const std::vector<line> &lines;
    int label_width = 0;
    int icon_width = 0;
};

auto draw_box( const catacurses::window &w, const box_spec &box ) -> void
{
    const auto &[at, inner, lines, label_width, icon_width] = box;
    const auto frame = frame_for( unicode_locale(), get_option<bool>( "UI_ROUNDED_BORDERS" ) );
    // Build the border and blank fill strings once per box, not once per row.
    std::string top_bar = frame.top_left;
    std::string bot_bar = frame.bottom_left;
    for( int i = 0; i < inner + 2; i++ ) {
        top_bar += frame.horizontal;
        bot_bar += frame.horizontal;
    }
    top_bar += frame.top_right;
    bot_bar += frame.bottom_right;
    const auto blank = std::string( inner + 2, ' ' );
    mvwprintz( w, at, c_dark_gray, top_bar );
    for( size_t i = 0; i < lines.size(); i++ ) {
        const auto row = at + point( 0, i + 1 );
        mvwprintz( w, row, c_dark_gray, frame.vertical );
        mvwprintz( w, row + point( 1, 0 ), c_black, blank );
        const auto &entry = lines[i];
        if( label_width > 0 ) {
            mvwprintz( w, row + point( 2, 0 ), entry.icon_color, entry.icon );
            const auto label_at = row + point( 2 + icon_width, 0 );
            mvwprintz( w, label_at, c_light_gray, entry.label );
            mvwprintz( w, label_at + point( label_width, 0 ), c_dark_gray, " | " );
            trim_and_print( w, label_at + point( label_width + 3, 0 ),
                            inner - icon_width - label_width - 3, entry.text_color, entry.text );
        } else {
            mvwprintz( w, row + point( 2, 0 ), entry.icon_color, entry.icon );
            // A fixed icon column keeps text aligned when icons differ in width.
            const auto prefix = icon_width > 0 ? icon_width : entry.icon_w > 0 ? entry.icon_w + 1 : 0;
            trim_and_print( w, row + point( 2 + prefix, 0 ), inner - prefix,
                            entry.text_color, entry.text );
        }
        mvwprintz( w, row + point( inner + 3, 0 ), c_dark_gray, frame.vertical );
    }
    mvwprintz( w, at + point( 0, lines.size() + 1 ), c_dark_gray, bot_bar );
}

struct placement {
    point at = point_zero;
    int inner = 0;
    int rows = 0;
    int label_width = 0;
    int icon_width = 0;

    auto width() const -> int { return inner + 4; }
    auto height() const -> int { return rows + 2; }
};

struct layout_input {
    int width;
    int height;
    std::array<std::string, 3> corners;
    int label_width;
    int weather_inner;
    int combat_inner;
    bool ascii;
    bool bars;
    /// Status box rows with and without the needs.
    int combat_rows;
    int combat_rows_lean;
    int vehicle_rows;
};

struct layout {
    std::array<placement, 3> boxes;
    bool needs = false;
    bool bars = false;
    /// A one-row status bar only carries the needs summary when it fits.
    bool bar_needs = false;
};

auto overlaps( const placement &a, const placement &b ) -> bool
{
    return a.at.x < b.at.x + b.width() && b.at.x < a.at.x + a.width() &&
    a.at.y < b.at.y + b.height() && b.at.y < a.at.y + a.height();
}

/// Share fit decisions with sidebar visibility.
auto calculate_layout( const layout_input &input ) -> layout
{
    auto result = layout{};
    auto used = std::array<int, 4> {};
    constexpr auto corners = std::array{ "top_left", "top_right", "bottom_left", "bottom_right" };
    const auto roomy = input.width >= 54;
    const auto center = placement{
        .at = point( input.width / 2 - 1, input.height / 2 - 1 ), .inner = -1, .rows = 1
    };
    for( auto index = size_t{ 0 }; index < result.boxes.size(); ++index ) {
        const auto &corner = input.corners[index];
        const auto found = std::ranges::find( corners, corner );
        if( found == corners.end() || ( index == 2 && input.vehicle_rows == 0 ) ) {
            continue;
        }
        const auto corner_index = static_cast<size_t>( found - corners.begin() );
        auto candidate = placement{};
        if( index == 0 ) {
            candidate.inner = input.weather_inner;
            candidate.rows = input.bars ? 1 : 4;
        } else if( index == 1 ) {
            if( input.bars ) {
                candidate.inner = input.combat_inner;
                candidate.rows = 1;
            } else {
                // Icons identify the rows, so labels are only for the text-only set.
                candidate.label_width = input.ascii ? input.label_width : 0;
                candidate.icon_width = input.ascii ? 0 : 3;
                candidate.inner = ( input.ascii ? input.label_width + 3 : candidate.icon_width ) +
                                  ( roomy ? 20 : 16 );
                candidate.rows = input.combat_rows;
            }
        } else {
            candidate.inner = roomy ? 32 : 28;
            candidate.rows = input.vehicle_rows;
        }
        const auto fits = [&]() {
            candidate.at = point( corner.ends_with( "right" ) ? input.width - candidate.width() : 0,
                                  corner.starts_with( "bottom" ) ?
                                  input.height - used[corner_index] - candidate.height() : used[corner_index] );
            return candidate.at.x >= 0 && candidate.at.y >= 0 &&
                   candidate.at.x + candidate.width() <= input.width &&
                   candidate.at.y + candidate.height() <= input.height &&
                   !overlaps( candidate, center ) &&
            std::ranges::none_of( result.boxes, [&]( const auto & other ) {
                return other.rows > 0 && overlaps( candidate, other );
            } );
        };
        auto accepted = fits();
        if( !accepted && index == 1 && !input.bars ) {
            candidate.rows = input.combat_rows_lean;
            accepted = fits();
        }
        if( accepted ) {
            result.boxes[index] = candidate;
            used[corner_index] += candidate.height();
            if( index == 1 ) {
                result.needs = input.bars || candidate.rows == input.combat_rows;
            }
        }
    }
    return result;
}

struct current_plan {
    layout geometry;
    vehicle_state vehicle;
};

auto plan_for( const avatar &you ) -> current_plan
{
    if( hud_sidebar::active() ) {
    return {};
}
const auto width = is_draw_tiles_mode() ? TERRAIN_WINDOW_TERM_WIDTH :
                   g->w_terrain ? getmaxx( g->w_terrain ) : 0;
const auto height = is_draw_tiles_mode() ? TERRAIN_WINDOW_TERM_HEIGHT :
                    g->w_terrain ? getmaxy( g->w_terrain ) : 0;
const auto corners = std::array{
    get_option<std::string>( "HUD_WEATHER_BOX" ),
    get_option<std::string>( "HUD_COMBAT_BOX" ),
    get_option<std::string>( "HUD_VEHICLE_BOX" )
};
auto label_width = 0;
for( const auto *label : {
    _( "Weapon" ), _( "Style" ), _( "Stance" ), _( "Needs" ), _( "Pain" ),
        _( "Thirst" ), _( "Hunger" ), _( "Rest" ), _( "Body temp" ), _( "Mana" )
    } ) {
        label_width = std::max( label_width, utf8_width( label ) );
    }
    auto vehicle = corners[2] == "off" ? vehicle_state{} :
                   current_vehicle( you );
    const auto icons = get_option<std::string>( "HUD_ICONS" );
    const auto ascii = icons == "ascii";
    const auto bars = compact_bars();
    // Size every weather row; a floor keeps the box from twitching as the hour's name changes.
    auto weather_inner = 0;
    if( corners[0] != "off" ) {
    if( bars ) {
            weather_inner = weather_bar_width( you, icons );
        } else {
            weather_inner = 26;
            for( const auto &row : weather_lines( you, icons ) ) {
                weather_inner = std::max( weather_inner, row.icon_w + ( row.icon_w > 0 ? 1 : 0 ) +
                                          utf8_width( row.text, true ) );
            }
        }
    }
    // The needs summary is the widest part of the status bar, and the sidebar keeps its own
    // needs panel, so the bar drops it rather than being pushed off the map.
    auto bar_needs = false;
    auto combat_inner = 0;
    auto combat_rows = 0;
    auto combat_rows_lean = 0;
    if( corners[1] != "off" && bars ) {
    const auto full = combat_bar_width( you, icons, true );
        bar_needs = full + 4 <= width;
        combat_inner = bar_needs ? full : combat_bar_width( you, icons, false );
    } else if( corners[1] != "off" ) {
    combat_rows = static_cast<int>( combat_lines( you, icons, true ).size() );
        combat_rows_lean = static_cast<int>( combat_lines( you, icons, false ).size() );
    }
    auto geometry = calculate_layout( {
        .width = width, .height = height, .corners = corners,
        .label_width = label_width, .weather_inner = weather_inner,
        .combat_inner = combat_inner, .ascii = ascii, .bars = bars,
        .combat_rows = combat_rows, .combat_rows_lean = combat_rows_lean,
        .vehicle_rows = vehicle.rows
    } );
    geometry.bars = bars;
    geometry.bar_needs = bar_needs;
    return { .geometry = geometry, .vehicle = std::move( vehicle ) };
}

} // namespace

namespace hud_windows
{

namespace
{

/// Stable ids: the save file and the Sidebar Options menu use these, never translated names.
constexpr auto weather_id = "weather";
constexpr auto combat_id = "combat";
constexpr auto needs_id = "needs";
constexpr auto limbs_id = "limbs";
constexpr auto stats_id = "stats";
constexpr auto movement_id = "movement";
constexpr auto weight_id = "weight";
constexpr auto compass_id = "compass";
constexpr auto log_id = "log";
constexpr auto vehicle_id = "vehicle";

/// Title plus body of one window, built fresh every draw.
struct content {
    std::string id;
    std::string name;
    /// One line of live state on the title row, so a collapsed window still reads.
    std::string summary;
    std::vector<line> body;
    /// False while the window has nothing to report, e.g. the vehicle window on foot.
    bool applicable = true;
    int label_width = 0;
    int icon_width = 0;
    int inner = 0;
};

/// A drawn window's cells, kept for mouse hit testing until the next draw.
struct hit_box {
    std::string id;
    point at = point_zero;
    int inner = 0;
    int rows = 0;
    bool collapsed = false;
    bool grabbed = false;
    /// Relative column just past the window name on the title row.  A collapsed window
    /// expands when this part is clicked; the rest of the row is its drag handle.
    int title_name_end = 0;

    auto width() const -> int {
        return inner + 4;
    }
    auto height() const -> int {
        return collapsed ? 3 : rows + 3;
    }
};

std::vector<hit_box> geometry;
std::vector<std::string> last_shown;
std::vector<std::string> last_skipped;
std::optional<std::string> grabbed_id;
point grab_offset;
vehicle_provider vehicle_body_provider;

/// Whether the window starts on.  The four former map boxes inherit their corner option;
/// the sidebar readings start floated so the new layout is the complete HUD.
auto default_visible( const std::string &id ) -> bool
{
    if( id == weather_id ) {
        return get_option<std::string>( "HUD_WEATHER_BOX" ) != "off";
    }
    if( id == combat_id || id == needs_id ) {
        return get_option<std::string>( "HUD_COMBAT_BOX" ) != "off";
    }
    if( id == vehicle_id ) {
        return get_option<std::string>( "HUD_VEHICLE_BOX" ) != "off";
    }
    return true;
}

/// The corner whose option seeds a window's first placement.
auto corner_for( const std::string &id ) -> std::string
{
    if( id == weather_id ) {
        return get_option<std::string>( "HUD_WEATHER_BOX" );
    }
    if( id == combat_id || id == needs_id ) {
        return get_option<std::string>( "HUD_COMBAT_BOX" );
    }
    if( id == limbs_id || id == stats_id || id == movement_id ) {
        return "top_right";
    }
    if( id == weight_id || id == compass_id ) {
        return "bottom_left";
    }
    if( id == log_id ) {
        return "bottom_right";
    }
    return get_option<std::string>( "HUD_VEHICLE_BOX" );
}

auto state_for( const avatar &you, const std::string &id ) -> state
{
    const auto found = you.hud_layout().find( id );
    if( found != you.hud_layout().end() ) {
        return found->second;
    }
    return state{
        .visible = default_visible( id )
    };
}

auto mutable_state( avatar &you, const std::string &id ) -> state &
{
    const auto found = you.hud_layout().find( id );
    if( found != you.hud_layout().end() ) {
        return found->second;
    }
    const auto defaults = state{
        .visible = default_visible( id )
    };
    return you.hud_layout().emplace( id, defaults ).first->second;
}

/// Sets the window above every saved peer, so the next draw paints it last.
auto raise_window( avatar &you, const std::string &id ) -> void
{
    auto &state = mutable_state( you, id );
    auto highest = 0;
    for( const auto &entry : you.hud_layout() ) {
        highest = std::max( highest, entry.second.order );
    }
    state.order = highest + 1;
}

auto map_size( const catacurses::window &w ) -> point
{
    if( is_draw_tiles_mode() ) {
        return point( TERRAIN_WINDOW_TERM_WIDTH, TERRAIN_WINDOW_TERM_HEIGHT );
    }
    return w ? point( getmaxx( w ), getmaxy( w ) ) : point_zero;
}

auto weather_content( const avatar &you, const std::string &icons ) -> content
{
    auto out = content{
        .id = weather_id, .name = _( "Weather" )
    };
    const auto underground = you.bub_pos().z() < 0;
    out.summary = time_text( you ) + "  " + weather_text( you, underground );
    // The condition and clock are the title; the body keeps the remaining readings.
    const auto clock = icons == "ascii" ? std::string() : glyph( icon::clock, icons );
    auto date = season_day_text();
    if( !underground ) {
        date += "  " + sky_track( icons );
    }
    out.body.push_back( {
        .icon = clock, .icon_w = utf8_width( clock ), .icon_color = c_light_gray,
        .text = date, .text_color = c_light_gray
    } );
    const auto light = get_light_level( character_funcs::fine_detail_vision_mod( you ) );
    const auto light_icon = icons == "ascii" ? std::string() : glyph( icon::light, icons );
    out.body.push_back( {
        .icon = light_icon, .icon_w = utf8_width( light_icon ), .icon_color = light.second,
        .text = string_format( _( "Light: %s" ), light.first ), .text_color = light.second
    } );
    const auto wind = wind_text( you, icons == "ascii" );
    const auto wind_icon = icons == "ascii" ? std::string() : glyph( icon::wind, icons );
    out.body.push_back( {
        .icon = wind_icon, .icon_w = utf8_width( wind_icon ), .icon_color = wind.color,
        .text = string_format( _( "Wind: %s" ), wind.text ), .text_color = wind.color
    } );
    out.icon_width = icons == "ascii" ? 0 : 3;
    return out;
}

auto combat_content( const avatar &you, const std::string &icons ) -> content
{
    auto out = content{
        .id = combat_id, .name = _( "Combat" )
    };
    const auto name = you.is_armed() ? character_funcs::fmt_wielded_weapon( you ) :
                      std::string( _( "fists" ) );
    auto stance = _( "Walking" );
    if( you.movement_mode_is( CMM_RUN ) ) {
        stance = _( "Running" );
    } else if( you.movement_mode_is( CMM_CROUCH ) ) {
        stance = _( "Crouching" );
    } else if( you.movement_mode_is( CMM_PRONE ) ) {
        stance = _( "Prone" );
    }
    out.summary = name + "  " + stance;
    // Weapon and stance name the title row; style and mana stay in the body.
    const auto lines = combat_lines( you, icons, false );
    for( size_t i = 2; i < lines.size(); ++i ) {
        out.body.push_back( lines[i] );
    }
    const auto ascii = icons == "ascii";
    out.icon_width = ascii ? 0 : 3;
    if( ascii ) {
        for( const auto &row : out.body ) {
            out.label_width = std::max( out.label_width, utf8_width( row.label ) );
        }
    }
    return out;
}

auto needs_content( const avatar &you, const std::string &icons ) -> content
{
    auto out = content{
        .id = needs_id, .name = _( "Needs" )
    };
    out.icon_width = icons == "ascii" ? 0 : 3;
    const auto needs = pressing_needs( you );
    if( needs.empty() ) {
        // The sidebar's needs panel shows a "Needs met" row; keep a body row so [-]
        // also has something to hide.
        out.summary = _( "Needs met" );
        const auto symbol = icons == "ascii" ? std::string() : glyph( icon::needs_met, icons );
        out.body.push_back( {
            .icon = symbol, .icon_w = utf8_width( symbol ), .icon_color = c_green,
            .text = _( "Needs met" ), .text_color = c_green
        } );
        return out;
    }
    for( const auto &need : needs ) {
        if( !out.summary.empty() ) {
            out.summary += "  ";
        }
        out.summary += need.label;
    }
    // Glyphs name each pressing need; the adjective would not fit a compact row.
    for( const auto &need : needs ) {
        const auto symbol = icons == "ascii" ? std::string() : glyph( need.symbol, icons );
        out.body.push_back( {
            .icon = symbol, .icon_w = utf8_width( symbol ), .icon_color = need.value.color,
            .text = need.label, .text_color = need.value.color
        } );
    }
    return out;
}

auto vehicle_content( const avatar &you, const std::string &icons ) -> content
{
    auto out = content{
        .id = vehicle_id, .name = _( "Vehicle" )
    };
    if( vehicle_body_provider ) {
        const auto reading = vehicle_body_provider( you );
        out.applicable = reading.applicable;
        if( !out.applicable ) {
            return out;
        }
        out.summary = reading.summary;
        out.icon_width = reading.icon_width;
        for( const auto &row : reading.body ) {
            out.body.push_back( {
                .icon = row.icon, .icon_w = utf8_width( row.icon ),
                .icon_color = row.icon_color, .text = row.text,
                .text_color = row.text_color
            } );
        }
        return out;
    }
    const auto state = current_vehicle( you );
    out.applicable = state.veh != nullptr;
    if( !out.applicable ) {
        return out;
    }
    const auto *veh = state.veh;
    out.summary = string_format( _( "Speed: %d %s" ),
                                 static_cast<int>( convert_velocity( veh->velocity, VU_VEHICLE ) ),
                                 velocity_units( VU_VEHICLE ) );
    auto lines = vehicle_lines( state, icons );
    // The speed is the title row already.
    if( lines.size() > 1 ) {
        lines.erase( lines.begin() + 1 );
    }
    out.body = std::move( lines );
    out.icon_width = icons == "ascii" ? 0 : 3;
    return out;
}

const efftype_id effect_bandaged( "bandaged" );
const efftype_id effect_bite( "bite" );
const efftype_id effect_bleed( "bleed" );
const efftype_id effect_disinfected( "disinfected" );
const efftype_id effect_infected( "infected" );
const efftype_id effect_mending( "mending" );

/// The worst problem with one limb, in the body panel's order; empty when healthy.
auto wound_for( const avatar &you, const bodypart_id &bp )
-> std::optional<std::pair<std::string, nc_color>>
{
    auto out = std::optional<std::pair<std::string, nc_color>>();
    if( you.get_part_hp_cur( bp ) <= 0 ) {
        out.emplace( you.has_effect( effect_mending, bp.id() ) ? std::string( _( "mending" ) ) :
                     std::string( _( "broken" ) ), c_magenta );
    } else if( you.has_effect( effect_bleed, bp.id() ) ) {
        out.emplace( std::string( _( "bleeding" ) ), c_red );
    } else if( you.has_effect( effect_infected, bp.id() ) ) {
        out.emplace( std::string( _( "infected" ) ), c_light_red );
    } else if( you.has_effect( effect_bite, bp.id() ) ) {
        out.emplace( std::string( _( "bitten" ) ), c_yellow );
    } else if( you.has_effect( effect_bandaged, bp.id() ) ) {
        out.emplace( std::string( _( "bandaged" ) ), c_light_green );
    } else if( you.has_effect( effect_disinfected, bp.id() ) ) {
        out.emplace( std::string( _( "disinfected" ) ), c_light_cyan );
    }
    return out;
}

auto limb_bar( const avatar &you, const bodypart_id &bp ) -> std::pair<std::string, nc_color>
{
    const auto hp = get_hp_bar( you.get_part_hp_cur( bp ), you.get_part_hp_max( bp ) );
    auto bar = hp.first;
    bar.append( static_cast<size_t>( std::max( 0, 5 - utf8_width( hp.first ) ) ), '.' );
    return { std::move( bar ), hp.second };
}

auto limbs_content( const avatar &you ) -> content
{
    auto out = content{
        .id = limbs_id, .name = _( "Limbs" )
    };
    auto wounded = 0;
    for( const auto &bp : you.get_all_body_parts( true ) ) {
        const auto bar = limb_bar( you, bp );
        auto text = body_part_hp_bar_ui_text( bp ) + " " + bar.first;
        auto color = bar.second;
        if( const auto wound = wound_for( you, bp ) ) {
            text += " " + wound->first;
            color = wound->second;
            wounded++;
        }
        out.body.push_back( {
            .text = std::move( text ), .text_color = color
        } );
    }
    out.summary = wounded > 0 ? string_format( _( "%d wounded" ), wounded ) :
                  std::string( _( "No wounds" ) );
    return out;
}

auto power_reading( const avatar &you ) -> std::pair<nc_color, std::string>
{
    auto color = c_red;
    auto text = std::string();
    if( !you.has_max_power() ) {
        return std::make_pair( c_light_gray, std::string( "--" ) );
    }
    if( you.get_power_level() >= you.get_max_power_level() / 2 ) {
        color = c_light_blue;
    } else if( you.get_power_level() >= you.get_max_power_level() / 3 ) {
        color = c_yellow;
    } else if( you.get_power_level() >= you.get_max_power_level() / 4 ) {
        color = c_red;
    }
    if( you.get_power_level() < 1_kJ ) {
        text = std::to_string( units::to_joule( you.get_power_level() ) ) +
               pgettext( "energy unit: joule", "J" );
    } else {
        text = std::to_string( units::to_kilojoule( you.get_power_level() ) ) +
               pgettext( "energy unit: kilojoule", "kJ" );
    }
    return { color, text };
}

/// Safe-mode readout colour, matching the sidebar Stats panel.
auto safe_color() -> nc_color
{
    auto color = g->safe_mode == SAFE_MODE_STOP ? c_yellow :
                 g->safe_mode == SAFE_MODE_ON ? c_green : c_red;
    if( g->safe_mode == SAFE_MODE_OFF && get_option<bool>( "AUTOSAFEMODE" ) ) {
        const auto returns = get_option<int>( "AUTOSAFEMODETURNS" );
        const auto percent = returns > 0 ? g->turnssincelastmon * 100 / returns : 100;
        if( percent >= 100 ) {
            color = c_green;
        } else if( percent >= 75 ) {
            color = c_yellow;
        } else if( percent >= 50 ) {
            color = c_light_red;
        } else if( percent >= 25 ) {
            color = c_red;
        }
    }
    return color;
}

auto stats_content( const avatar &you ) -> content
{
    auto out = content{
        .id = stats_id, .name = _( "Stats" )
    };
    const auto stat_row = [&]( const char *label, const int base, const int value ) {
        out.body.push_back( {
            .text = string_format( "%s %s", _( label ), value_trimmed( value ) ),
            .text_color = color_compare_base( base, value )
        } );
    };
    stat_row( "Str", you.get_str_base(), you.get_str() );
    stat_row( "Dex", you.get_dex_base(), you.get_dex() );
    stat_row( "Int", you.get_int_base(), you.get_int() );
    stat_row( "Per", you.get_per_base(), you.get_per() );
    const auto power = power_reading( you );
    out.body.push_back( {
        .text = string_format( _( "Power %s" ), power.second ), .text_color = power.first
    } );
    out.body.push_back( {
        .text = string_format( _( "Safe: %s" ), g->safe_mode ? _( "On" ) : _( "Off" ) ),
        .text_color = safe_color()
    } );
    out.summary = string_format( _( "Str %d Dex %d Int %d Per %d" ),
                                 you.get_str(), you.get_dex(), you.get_int(), you.get_per() );
    return out;
}

auto move_mode_letter( const avatar &you ) -> std::string
{
    if( you.movement_mode_is( CMM_RUN ) ) {
        return pgettext( "movement-type", "R" );
    }
    if( you.movement_mode_is( CMM_CROUCH ) ) {
        return pgettext( "movement-type", "C" );
    }
    if( you.movement_mode_is( CMM_PRONE ) ) {
        return pgettext( "movement-type", "P" );
    }
    return pgettext( "movement-type", "W" );
}

/// The Movement panel's sound reading, including the ambient subtraction its option asks for.
auto sound_text( const avatar &you ) -> std::string
{
    const auto option = get_option<std::string>( "SOUND_DISPLAY_TYPE" );
    if( option == "decibels" ) {
        return std::to_string( you.volume );
    }
    const auto &weather = get_weather();
    const short weather_vol = weather.weather_id->sound_attn;
    const short wind_volume = std::min( 150, weather.windspeed );
    const auto indoor = ( AMBIENT_VOLUME_ABOVEGROUND + dBspl_to_mdBspl( 2 * weather_vol ) ) / 100;
    const auto outdoor = ( AMBIENT_VOLUME_ABOVEGROUND +
                           dBspl_to_mdBspl( wind_volume + weather_vol ) ) / 100;
    const auto ambient = get_map().is_outside( you.bub_pos() ) ? outdoor : indoor;
    if( option == "relative_decibels" ) {
        return std::to_string( you.volume - ambient );
    }
    return std::to_string( average_minvol_distance( 0, ( you.volume - ambient ) * 100, 0, 0 ) );
}

auto movement_content( const avatar &you ) -> content
{
    auto out = content{
        .id = movement_id, .name = _( "Movement" )
    };
    const auto mode = move_mode_letter( you );
    out.summary = string_format( _( "Move %d(%s)" ), you.movecounter, mode );
    const auto stamina = get_hp_bar( you.get_stamina(), you.get_stamina_max() );
    auto bar = stamina.first;
    bar.append( static_cast<size_t>( std::max( 0, 5 - utf8_width( stamina.first ) ) ), '.' );
    out.body.push_back( {
        .text = string_format( _( "Speed %d" ), you.get_speed() ), .text_color = c_light_gray
    } );
    out.body.push_back( {
        .text = string_format( _( "Sound %s  Stam %s" ), sound_text( you ), bar ),
        .text_color = stamina.second
    } );
    out.body.push_back( {
        .text = string_format( _( "Mood %d  Focus %d" ), you.get_morale_level(),
                               you.focus_pool ),
        .text_color = c_light_gray
    } );
    return out;
}

auto carry_weight_text( const avatar &you ) -> std::string
{
    return string_format( "%.1f/%.1f", round_up( convert_weight( you.weight_carried() ), 1 ),
                          round_up( convert_weight( you.weight_capacity() ), 1 ) );
}

auto carry_volume_text( const avatar &you ) -> std::string
{
    return string_format( "%.2f/%.2f",
                          round_up( convert_volume( to_milliliter( you.volume_carried() ) ), 2 ),
                          round_up( convert_volume( to_milliliter( you.volume_capacity() ) ), 2 ) );
}

auto weight_color( const avatar &you ) -> nc_color
{
    if( you.weight_carried() > you.weight_capacity() ) {
        return c_red;
    }
    return you.weight_carried() > you.weight_capacity() * 0.75 ? c_yellow : c_light_gray;
}

auto volume_color( const avatar &you ) -> nc_color
{
    if( you.volume_carried() > you.volume_capacity() * 0.85 ) {
        return c_red;
    }
    return you.volume_carried() > you.volume_capacity() * 0.65 ? c_yellow : c_light_gray;
}

auto weight_content( const avatar &you ) -> content
{
    auto out = content{
        .id = weight_id, .name = _( "Weight" )
    };
    const auto weight = carry_weight_text( you );
    const auto volume = carry_volume_text( you );
    out.body.push_back( {
        .text = string_format( _( "Weight %s" ), weight ), .text_color = weight_color( you )
    } );
    out.body.push_back( {
        .text = string_format( _( "Volume %s" ), volume ), .text_color = volume_color( you )
    } );
    out.summary = string_format( _( "Wgt %s  Vol %s" ), weight, volume );
    return out;
}

auto compass_content( const avatar &you ) -> content
{
    auto out = content{
        .id = compass_id, .name = _( "Compass" )
    };
    // Mirror the sidebar compass: direction labels, visible symbols and threat colours.
    static constexpr auto labels = std::array<const char *, 9> {
        "North:", "NE:", "East:", "SE:", "South:", "SW:", "West:", "NW:", "Near:"
    };
    const auto &sight = you.get_mon_visible();
    auto summary = std::string();
    for( int i = 0; i < 9; i++ ) {
        auto text = std::string( _( labels[i] ) ) + " ";
        auto count = static_cast<int>( sight.unique_types[i].size() );
        for( size_t n = 0; n < sight.unique_types[i].size(); n++ ) {
            text += "@";
        }
        for( const auto &mon : sight.unique_mons[i] ) {
            text += mon.first->sym;
            count += mon.second;
        }
        const auto empty = count <= 0;
        const auto dangerous = i < 8 && sight.dangerous[i];
        out.body.push_back( {
            .text = empty ? text + "-" : text + string_format( " %d", count ),
            .text_color = empty ? c_dark_gray : dangerous ? c_light_red : c_light_gray
        } );
        if( !empty ) {
            if( !summary.empty() ) {
                summary += " ";
            }
            summary += string_format( "%s%d", i == 8 ? _( "Near" ) : _( labels[i] ), count );
        }
    }
    out.summary = summary.empty() ? std::string( _( "Clear" ) ) : summary;
    return out;
}

auto log_content( const int max_inner ) -> content
{
    auto out = content{
        .id = log_id, .name = _( "Log" )
    };
    constexpr auto body_rows = 10;
    const auto fold_width = std::clamp( max_inner - 2, 6, 44 );
    const auto recent = Messages::recent_messages( 10 );
    auto lines = std::vector<std::string>();
    for( const auto &msg : recent ) {
        // Colour tags stay; the log window prints them with print_colored_text.
        for( auto &line : foldstring( msg.second, fold_width ) ) {
            lines.push_back( std::move( line ) );
        }
    }
    const auto visible_lines = std::min( body_rows, static_cast<int>( lines.size() ) );
    for( auto i = 0; i < body_rows - visible_lines; ++i ) {
        out.body.push_back( {
            .text = std::string(), .text_color = c_light_gray
        } );
    }
    for( auto i = static_cast<int>( lines.size() ) - visible_lines;
         i < static_cast<int>( lines.size() ); ++i ) {
        out.body.push_back( {
            .text = lines[static_cast<size_t>( i )], .text_color = c_light_gray
        } );
    }
    out.summary = recent.empty() ? std::string( _( "No messages" ) ) :
                  utf8_truncate( remove_color_tags( recent.back().second ), 24 );
    return out;
}

/// Width every row needs, title row included, capped to the map area.
auto finish( content &c, const int max_inner ) -> void
{
    auto body_inner = 0;
    for( const auto &row : c.body ) {
        const auto text = utf8_width( row.text, true );
        if( c.label_width > 0 ) {
            body_inner = std::max( body_inner, c.icon_width + c.label_width + 3 + text );
        } else {
            const auto prefix = c.icon_width > 0 ? c.icon_width :
                                row.icon_w > 0 ? row.icon_w + 1 : 0;
            body_inner = std::max( body_inner, prefix + text );
        }
    }
    const auto title_inner = utf8_width( c.name ) + utf8_width( c.summary, true ) + 6;
    c.inner = std::clamp( std::max( {
        body_inner, title_inner, 10
    } ), 10, std::max( 10, max_inner ) );
}

struct cell_rect {
    point at;
    int width = 0;
    int height = 0;
};

auto rects_overlap( const point at, const int width, const int height,
                    const std::vector<cell_rect> &rects ) -> bool
{
    return std::ranges::any_of( rects, [&]( const cell_rect & other ) {
        return at.x < other.at.x + other.width && other.at.x < at.x + width &&
               at.y < other.at.y + other.height && other.at.y < at.y + height;
    } );
}

/// Stacks windows that share a corner, then slides past anything the player already placed.
/// Nothing is placed until the player moves a window, so reading the defaults is deterministic.
auto default_at( const std::string &id, const point map, const int width, const int height,
                 const std::vector<cell_rect> &occupied ) -> point
{
    auto corner = corner_for( id );
    if( corner == "off" ) {
        corner = "top_left";
    }
    const auto right = corner.ends_with( "right" );
    const auto bottom = corner.starts_with( "bottom" );
    auto at = point( right ? map.x - width : 0, bottom ? map.y - height : 0 );
    for( int step = 0; step <= map.y; ++step ) {
        if( !rects_overlap( at, width, height, occupied ) ) {
            break;
        }
        at.y += bottom ? -1 : 1;
        at.y = std::clamp( at.y, 0, std::max( 0, map.y - height ) );
    }
    return at;
}

auto control_columns( const hit_box &box ) -> std::pair<int, int>
{
    // `[-]` sits one column in from the right border.
    return { box.inner - 1, box.inner + 1 };
}

auto paint( const catacurses::window &target, const content &c, const hit_box &box ) -> void
{
    const auto frame = frame_for( unicode_locale(), get_option<bool>( "UI_ROUNDED_BORDERS" ) );
    std::string top = frame.top_left;
    std::string bottom = frame.bottom_left;
    for( int i = 0; i < c.inner + 2; i++ ) {
        top += frame.horizontal;
        bottom += frame.horizontal;
    }
    top += frame.top_right;
    bottom += frame.bottom_right;
    mvwprintz( target, box.at, c_dark_gray, top );
    const auto title_row = box.at + point( 0, 1 );
    mvwprintz( target, title_row, c_dark_gray, frame.vertical );
    mvwprintz( target, title_row + point( 1, 0 ), c_black, std::string( c.inner + 2, ' ' ) );
    mvwprintz( target, title_row + point( 2, 0 ), box.grabbed ? c_yellow : c_white, c.name );
    const auto summary_at = 2 + utf8_width( c.name ) + 2;
    const auto summary_width = std::max( 0, box.inner - 2 - summary_at );
    if( summary_width > 0 ) {
        trim_and_print( target, title_row + point( summary_at, 0 ), summary_width,
                        c_light_gray, c.summary );
    }
    mvwprintz( target, title_row + point( box.inner - 1, 0 ),
               box.collapsed ? c_light_green : c_light_red,
               box.collapsed ? "[+]" : "[-]" );
    mvwprintz( target, title_row + point( box.inner + 3, 0 ), c_dark_gray, frame.vertical );
    if( !box.collapsed ) {
        for( auto i = 0; i < box.rows; i++ ) {
            const auto row = box.at + point( 0, i + 2 );
            mvwprintz( target, row, c_dark_gray, frame.vertical );
            mvwprintz( target, row + point( 1, 0 ), c_black, std::string( c.inner + 2, ' ' ) );
            const auto &entry = c.body[static_cast<size_t>( i )];
            if( c.label_width > 0 ) {
                mvwprintz( target, row + point( 2, 0 ), entry.icon_color, entry.icon );
                const auto label_at = row + point( 2 + c.icon_width, 0 );
                mvwprintz( target, label_at, c_light_gray, entry.label );
                mvwprintz( target, label_at + point( c.label_width, 0 ), c_dark_gray, " | " );
                trim_and_print( target, label_at + point( c.label_width + 3, 0 ),
                                c.inner - c.icon_width - c.label_width - 3,
                                entry.text_color, entry.text );
            } else {
                mvwprintz( target, row + point( 2, 0 ), entry.icon_color, entry.icon );
                const auto prefix = c.icon_width > 0 ? c.icon_width :
                                    entry.icon_w > 0 ? entry.icon_w + 1 : 0;
                if( c.id == log_id ) {
                    // Message colours live in tags; the compact log keeps them.
                    auto color = entry.text_color;
                    print_colored_text( target, row + point( 2 + prefix, 0 ), color,
                                        entry.text_color, entry.text );
                } else {
                    trim_and_print( target, row + point( 2 + prefix, 0 ), c.inner - prefix,
                                    entry.text_color, entry.text );
                }
            }
            mvwprintz( target, row + point( c.inner + 3, 0 ), c_dark_gray, frame.vertical );
        }
    }
    mvwprintz( target, box.at + point( 0, box.height() - 1 ), c_dark_gray, bottom );
}

} // namespace

auto active() -> bool
{
    if( !get_option<bool>( "HUD_WINDOWS" ) || get_option<bool>( "HUD_CORNER_BARS" ) ) {
        return false;
    }
    // Classic and compact keep their own combined panels; the floating HUD belongs to the
    // modern layouts, including the first-run grouped one.
    const auto layout = panel_manager::get_manager().get_current_layout_id();
    return layout == "labels" || layout == "labels-narrow" || layout == "grouped";
}

auto visible( const avatar &you, const std::string &id ) -> bool
{
    return state_for( you, id ).visible;
}

auto shown( const std::string &id ) -> bool
{
    if( !active() || !visible( get_avatar(), id ) ) {
        return false;
    }
    if( std::ranges::find( last_shown, id ) != last_shown.end() ) {
        return true;
    }
    if( std::ranges::find( last_skipped, id ) != last_skipped.end() ) {
        return false;
    }
    // Not evaluated since the last draw (e.g. just enabled in the menu): assume the reading
    // moved to the window so the menu does not keep a phantom sidebar row.
    return true;
}

auto toggle( avatar &you, const std::string &id ) -> void
{
    auto &state = mutable_state( you, id );
    state.visible = !state.visible;
}

auto raise( avatar &you, const std::string &id ) -> void
{
    raise_window( you, id );
}

auto entries() -> std::vector<std::pair<std::string, std::string>>
{
    return {
        { weather_id, _( "Weather" ) }, { combat_id, _( "Combat" ) },
        { needs_id, _( "Needs" ) }, { limbs_id, _( "Limbs" ) },
        { stats_id, _( "Stats" ) }, { movement_id, _( "Movement" ) },
        { weight_id, _( "Weight" ) }, { compass_id, _( "Compass" ) },
        { log_id, _( "Log" ) }, { vehicle_id, _( "Vehicle" ) }
    };
}

auto draw( const avatar &you, const catacurses::window &w ) -> void
{
    geometry.clear();
    last_shown.clear();
    last_skipped.clear();
    if( !active() ) {
        grabbed_id.reset();
        return;
    }
    const auto map = map_size( w );
    // A map narrower than one minimum window cannot host the layout without covering the sidebar.
    if( map.x < 14 || map.y < 3 ) {
        grabbed_id.reset();
        return;
    }
    const auto icons = get_option<std::string>( "HUD_ICONS" );
    const auto max_inner = map.x - 4;
    // Content order is the default-placement and reservation order.  The vehicle window is
    // reserved first because its reading is the one a small terminal must keep; the log fills
    // in around it.  Painting follows the saved stacking order below.
    auto contents = std::array<content, 10> {
        vehicle_content( you, icons ), weather_content( you, icons ),
        combat_content( you, icons ), needs_content( you, icons ),
        limbs_content( you ), stats_content( you ), movement_content( you ),
        weight_content( you ), compass_content( you ), log_content( max_inner )
    };
    struct pending {
        content *body;
        hit_box box;
        bool placed = false;
        bool skip = false;
        int order = 0;
    };
    auto items = std::vector<pending>();
    // Placed windows reserve their cells first, so fresh windows never cover them.
    auto occupied = std::vector<cell_rect>();
    for( auto &c : contents ) {
        if( !c.applicable ) {
            // Evaluated and deliberately absent, e.g. the vehicle window on foot.
            last_skipped.push_back( c.id );
            continue;
        }
        const auto state = state_for( you, c.id );
        if( !state.visible ) {
            continue;
        }
        finish( c, max_inner );
        auto box = hit_box{
            .id = c.id, .at = point_zero, .inner = c.inner,
            .rows = static_cast<int>( c.body.size() ),
            .collapsed = state.collapsed,
            .grabbed = grabbed_id && *grabbed_id == c.id,
            .title_name_end = 2 + utf8_width( c.name ) + 1
        };
        if( state.placed ) {
            box.at = state.pos;
            box.at.x = std::clamp( box.at.x, 0, std::max( 0, map.x - box.width() ) );
            box.at.y = std::clamp( box.at.y, 0, std::max( 0, map.y - box.height() ) );
            occupied.push_back( { box.at, box.width(), box.height() } );
        }
        items.push_back( { &c, box, state.placed, false, state.order } );
    }
    // The legacy placer keeps the avatar's centre clear; do the same for fresh windows.
    occupied.push_back( {
        point( std::max( 0, map.x / 2 - 1 ), std::max( 0, map.y / 2 - 1 ) ),
        std::min( 3, map.x ), std::min( 3, map.y )
    } );
    for( auto &item : items ) {
        if( item.placed ) {
            continue;
        }
        item.box.at = default_at( item.box.id, map, item.box.width(), item.box.height(),
                                  occupied );
        item.box.at.x = std::clamp( item.box.at.x, 0,
                                    std::max( 0, map.x - item.box.width() ) );
        item.box.at.y = std::clamp( item.box.at.y, 0,
                                    std::max( 0, map.y - item.box.height() ) );
        if( rects_overlap( item.box.at, item.box.width(), item.box.height(), occupied ) ) {
            // No free cells: the sidebar keeps this reading instead of stacking windows.
            item.skip = true;
            last_skipped.push_back( item.box.id );
            continue;
        }
        occupied.push_back( { item.box.at, item.box.width(), item.box.height() } );
    }
    // Painting and hit testing follow the player's stacking order; equal orders keep the
    // default content order.
    std::stable_sort( items.begin(), items.end(), []( const pending &a, const pending &b ) {
        return a.order < b.order;
    } );
    static auto windows = std::array<catacurses::window, 10>();
    for( size_t index = 0; index < items.size(); ++index ) {
        if( items[index].skip ) {
            continue;
        }
        const auto &c = *items[index].body;
        auto &box = items[index].box;
        if( is_draw_tiles_mode() ) {
            auto &box_win = windows[index];
            const auto origin = point( getbegx( w ) + box.at.x, getbegy( w ) + box.at.y );
            if( !box_win || getmaxx( box_win ) != box.width() ||
                getmaxy( box_win ) != box.height() ||
                getbegx( box_win ) != origin.x || getbegy( box_win ) != origin.y ) {
                box_win = catacurses::newwin( box.height(), box.width(), origin );
            }
            werase( box_win );
            paint( box_win, c, {
                .id = box.id, .at = point_zero, .inner = box.inner, .rows = box.rows,
                .collapsed = box.collapsed, .grabbed = box.grabbed
            } );
            wnoutrefresh( box_win );
        } else {
            paint( w, c, box );
        }
        last_shown.push_back( box.id );
        geometry.push_back( box );
    }
}

auto secondary_clicked( avatar &you, const catacurses::window &w,
                        const point &map_cell ) -> bool
{
    if( !active() ) {
        return false;
    }
    const auto map = map_size( w );
    if( map_cell.x < 0 || map_cell.y < 0 || map_cell.x >= map.x || map_cell.y >= map.y ) {
        return false;
    }
    for( auto it = geometry.rbegin(); it != geometry.rend(); ++it ) {
        const auto &box = *it;
        if( map_cell.x >= box.at.x && map_cell.x < box.at.x + box.width() &&
            map_cell.y >= box.at.y && map_cell.y < box.at.y + box.height() ) {
            raise_window( you, box.id );
            return true;
        }
    }
    return false;
}

auto clicked( avatar &you, const catacurses::window &w, const point &map_cell ) -> bool
{
    if( !active() ) {
        return false;
    }
    const auto map = map_size( w );
    const auto rel = map_cell;
    if( rel.x < 0 || rel.y < 0 || rel.x >= map.x || rel.y >= map.y ) {
        if( grabbed_id ) {
            // A click outside the map drops the window where it was clamped.
            grabbed_id.reset();
            return true;
        }
        return false;
    }
    // Last drawn is on top.
    for( auto it = geometry.rbegin(); it != geometry.rend(); ++it ) {
        const auto &box = *it;
        if( rel.x < box.at.x || rel.x >= box.at.x + box.width() ||
            rel.y < box.at.y || rel.y >= box.at.y + box.height() ) {
            continue;
        }
        raise_window( you, box.id );
        if( rel.y == box.at.y + 1 ) {
            const auto [control_first, control_last] = control_columns( box );
            const auto column = rel.x - box.at.x;
            if( column >= control_first && column <= control_last ) {
                auto &state = mutable_state( you, box.id );
                state.collapsed = !state.collapsed;
                grabbed_id.reset();
                return true;
            }
            if( box.collapsed && column < box.title_name_end ) {
                // Clicking the name of a collapsed window restores it; the rest of the
                // title row stays a drag handle so a collapsed window can be moved.
                auto &state = mutable_state( you, box.id );
                state.collapsed = false;
                grabbed_id.reset();
                return true;
            }
            if( grabbed_id && *grabbed_id == box.id ) {
                grabbed_id.reset();
            } else {
                grabbed_id = box.id;
                grab_offset = rel - box.at;
            }
            return true;
        }
        // A body click belongs to the window, never to the map behind it.
        grabbed_id.reset();
        return true;
    }
    if( grabbed_id ) {
        grabbed_id.reset();
        return true;
    }
    return false;
}

auto pointer_moved( avatar &you, const catacurses::window &w, const point &map_cell ) -> bool
{
    if( !active() || !grabbed_id ) {
        return false;
    }
    const auto found = std::ranges::find( geometry, *grabbed_id, &hit_box::id );
    if( found == geometry.end() ) {
        grabbed_id.reset();
        return false;
    }
    const auto map = map_size( w );
    const auto rel = map_cell;
    auto target = rel - grab_offset;
    // The sidebar is outside the map window, so this clamp is also the sidebar guard.
    target.x = std::clamp( target.x, 0, std::max( 0, map.x - found->width() ) );
    target.y = std::clamp( target.y, 0, std::max( 0, map.y - found->height() ) );
    // Never hide any window completely: it would lose its title and [-] control.
    const auto covers_rect = []( const point a, const int aw, const int ah,
                                 const point b, const int bw, const int bh ) {
        return b.x >= a.x && b.y >= a.y && b.x + bw <= a.x + aw && b.y + bh <= a.y + ah;
    };
    const auto hides_a_window = [&]( const hit_box & other ) {
        return other.id != found->id &&
               ( covers_rect( target, found->width(), found->height(),
                              other.at, other.width(), other.height() ) ||
                 covers_rect( other.at, other.width(), other.height(),
                              target, found->width(), found->height() ) );
    };
    if( std::ranges::any_of( geometry, hides_a_window ) ) {
        return true;
    }
    auto &state = mutable_state( you, *grabbed_id );
    state.pos = target;
    state.placed = true;
    found->at = target;
    return true;
}

auto release() -> void
{
    grabbed_id.reset();
}

auto set_vehicle_provider( vehicle_provider provider ) -> void
{
    vehicle_body_provider = std::move( provider );
}

} // namespace hud_windows

namespace hud_boxes
{

auto mana_matters( const Character &you ) -> bool
{
    if( get_option<bool>( "ALWAYS_SHOW_MANA" ) ||
    you.magic->available_mana() < you.magic->max_mana( you ) ) {
    return true;
}
return std::ranges::any_of( you.magic->spells(), [&]( const spell_id & sp ) {
    return you.magic->get_spell( sp ).energy_source() == mana_energy;
    } );
}

auto mana_reading( const Character &you ) -> mana_text
{
    const auto max = you.magic->max_mana( you );
    if( max <= 0 ) {
        return { .text = "--", .color = c_light_gray };
    }
    const auto now = you.magic->available_mana();
    const auto color = now >= max / 2 ? c_light_blue : now >= max / 3 ? c_yellow : c_red;
    return { .text = string_format( "%d/%d", now, max ), .color = color };
}

auto weather_box_shown() -> bool
{
    if( hud_windows::active() ) {
        return hud_windows::shown( "weather" );
    }
    return !compact_bars() && plan_for( get_avatar() ).geometry.boxes[0].rows > 0;
}

auto weather_box_shows_environment() -> bool
{
    return weather_box_shown();
}

auto combat_box_shown() -> bool
{
    if( hud_windows::active() ) {
        return hud_windows::shown( "combat" );
    }
    return !compact_bars() && plan_for( get_avatar() ).geometry.boxes[1].rows > 0;
}

auto status_box_shows_needs() -> bool
{
    if( hud_windows::active() ) {
        return hud_windows::shown( "needs" );
    }
    return !compact_bars() && plan_for( get_avatar() ).geometry.needs;
}

auto combat_box_shows_mana( const Character &you ) -> bool
{
    if( hud_windows::active() ) {
        return hud_windows::shown( "combat" ) && mana_matters( you );
    }
    return !compact_bars() && combat_box_shown() && mana_matters( you );
}

auto vehicle_box_shown() -> bool
{
    if( hud_windows::active() ) {
        return hud_windows::shown( "vehicle" );
    }
    return plan_for( get_avatar() ).geometry.boxes[2].rows > 0;
}

auto draw( const avatar &you, const catacurses::window &w ) -> void
{
    if( hud_windows::active() ) {
        hud_windows::draw( you, w );
        return;
    }
    const auto plan = plan_for( you );
    const auto icons = get_option<std::string>( "HUD_ICONS" );
    static auto windows = std::array<catacurses::window, 3>();
    for( auto index = size_t{ 0 }; index < plan.geometry.boxes.size(); ++index ) {
        const auto &box = plan.geometry.boxes[index];
        if( box.rows == 0 ) {
            continue;
        }
        const auto lines = index == 0 ? weather_lines( you, icons ) :
                           index == 1 ? combat_lines( you, icons, plan.geometry.bars ?
                               plan.geometry.bar_needs : plan.geometry.needs ) :
                           vehicle_lines( plan.vehicle, icons );
        if( is_draw_tiles_mode() ) {
            auto &box_win = windows[index];
            const auto origin = point( getbegx( w ) + box.at.x, getbegy( w ) + box.at.y );
            if( !box_win || getmaxx( box_win ) != box.width() || getmaxy( box_win ) != box.height() ||
                getbegx( box_win ) != origin.x || getbegy( box_win ) != origin.y ) {
                box_win = catacurses::newwin( box.height(), box.width(), origin );
            }
            werase( box_win );
            draw_box( box_win, {
                .at = point_zero, .inner = box.inner, .lines = lines,
                .label_width = box.label_width, .icon_width = box.icon_width
            } );
            wnoutrefresh( box_win );
        } else {
            draw_box( w, {
                .at = box.at, .inner = box.inner, .lines = lines,
                .label_width = box.label_width, .icon_width = box.icon_width
            } );
        }
    }
}

} // namespace hud_boxes

namespace hud_sidebar
{

namespace
{

auto framed() -> bool { return TERMY >= 40; }

auto section_lines( const avatar &you, const section content ) -> std::vector<line>
{
    const auto icons = get_option<std::string>( "HUD_ICONS" );
    switch( content ) {
        case section::weather: {
            auto rows = weather_lines( you, icons );
            if( !framed() ) {
                auto &light = rows[2];
                const auto &wind = rows[3];
                const auto combined = colorize( light.text, light.text_color ) + " | " +
                                      colorize( wind.text, wind.text_color );
                if( utf8_width( combined, true ) <= 44 ) {
                    light.icon.clear();
                    light.icon_w = 0;
                    light.text = combined;
                    rows.pop_back();
                }
            }
            return rows;
        }
        case section::character:
            return combat_lines( you, icons, false );
        case section::vehicle:
            return vehicle_lines( current_vehicle( you ), icons );
        case section::needs:
            break;
    }
    auto out = std::vector<line>();
    const auto needs = pressing_needs( you );
    if( needs.empty() ) {
        const auto ic = icons == "ascii" ? std::string() : glyph( icon::needs_met, icons );
        out.push_back( { .icon = ic, .icon_w = utf8_width( ic ), .icon_color = c_green,
                         .text = _( "Needs met" ), .text_color = c_green } );
    } else if( !framed() ) {
        auto summary = std::string();
        for( const auto &need : needs ) {
            if( !summary.empty() ) {
                summary += " | ";
            }
            summary += colorize( need.label + " " + need.value.text, need.value.color );
        }
        for( auto &text : foldstring( summary, 44 ) ) {
            out.push_back( { .text = std::move( text ), .text_color = c_light_gray } );
        }
    } else {
        for( const auto &need : needs ) {
            const auto ic = icons == "ascii" ? std::string() : glyph( need.symbol, icons );
            out.push_back( { .icon = ic, .icon_w = utf8_width( ic ), .icon_color = need.value.color,
                             .text = need.value.text, .text_color = need.value.color,
                             .label = need.label } );
        }
    }
    return out;
}

auto title( const section content ) -> std::string
{
    switch( content ) {
    case section::weather:
        return _( "Weather" );
        case section::character:
            return _( "Character" );
        case section::needs:
            return _( "Needs" );
        case section::vehicle:
            return _( "Vehicle" );
    }
    return {};
}

} // namespace

auto active() -> bool
{
    return panel_manager::get_manager().get_current_layout_id() == "grouped";
}

auto height( const section content ) -> int
{
    const auto &you = get_avatar();
    auto rows = 0;
    switch( content ) {
        case section::weather:
            rows = framed() ? 4 : static_cast<int>( section_lines( you, content ).size() );
            break;
        case section::character:
            rows = 2 + !you.martial_arts_data->selected_is_none() + hud_boxes::mana_matters( you );
            break;
        case section::vehicle:
            rows = current_vehicle( you ).rows;
            break;
        case section::needs:
            rows = static_cast<int>( section_lines( you, content ).size() );
            break;
    }
    return rows + ( framed() ? 2 : 0 );
}

auto draw( avatar &you, const catacurses::window &w, const section content ) -> void
{
    werase( w );
    const auto lines = section_lines( you, content );
    const auto ascii = get_option<std::string>( "HUD_ICONS" ) == "ascii";
    auto label_width = 0;
    if( framed() && ( content == section::needs || ascii ) ) {
        for( const auto &row : lines ) {
            label_width = std::max( label_width, utf8_width( row.label ) );
        }
    }
    if( framed() && getmaxy( w ) >= static_cast<int>( lines.size() ) + 2 ) {
        draw_box( w, { .at = point_zero, .inner = getmaxx( w ) - 4, .lines = lines,
                       .label_width = label_width, .icon_width = ascii ? 0 : 3
                     } );
        trim_and_print( w, point( 2, 0 ), getmaxx( w ) - 4, c_light_gray, title( content ) );
    } else {
        for( auto row = 0; const auto &entry : lines ) {
            if( row >= getmaxy( w ) ) {
                break;
            }
            const auto prefix = entry.icon_w > 0 ? entry.icon_w + 1 : 0;
            mvwprintz( w, point( 0, row ), entry.icon_color, entry.icon );
            trim_and_print( w, point( prefix, row++ ), getmaxx( w ) - prefix, entry.text_color,
                            entry.label.empty() ? entry.text : entry.label + ": " + entry.text );
        }
    }
    wnoutrefresh( w );
}

} // namespace hud_sidebar

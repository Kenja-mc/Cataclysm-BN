#include "hud_boxes.h"

#include <algorithm>
#include <array>
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
#include "calendar.h"
#include "catacharset.h"
#include "character_functions.h"
#include "character_martial_arts.h"
#include "color.h"
#include "cursesdef.h"
#include "flag.h"
#include "game.h"
#include "item.h"
#include "magic/magic.h"
#include "needs_status.h"
#include "options.h"
#include "output.h"
#include "overmap/overmapbuffer_registry.h"
#include "panels_utility.h"
#include "string_formatter.h"
#include "translations.h"
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
    return get_option<bool>( "HUD_CORNER_BARS" );
}

enum class icon {
    sun, moon, cloud, rain, storm, snow, strange, underground, fists, melee, gun, bow, style,
    walk, run, crouch, prone, mana, compass, fuel, battery, pain, thirst, hunger, rest, heat
};

/// One glyph per icon for each icon set. Nerd Font glyphs are Material Design icons (the fist is Font Awesome).
auto glyph( const icon i, const std::string &style ) -> std::string
{
    const auto pick = [&]( const char *uni, const char *nerd, const char *ascii ) {
        return std::string( style == "nerd" ? nerd : style == "ascii" ? ascii : uni );
    };
    switch( i ) {
        case icon::sun:
            return pick( "☼", "\U000F0599", "o" );
        case icon::moon:
            return pick( "☾", "\U000F0594", "C" );
        case icon::cloud:
            return pick( "☁", "\U000F0590", "~" );
        case icon::rain:
            return pick( "☂", "\U000F0597", "/" );
        case icon::storm:
            return pick( "↯", "\U000F0593", "!" );
        case icon::snow:
            return pick( "❄", "\U000F0598", "*" );
        case icon::strange:
            return pick( "◎", "\U000F0591", "%" );
        case icon::underground:
            return pick( "▼", "▼", "v" );
        case icon::fists:
            return pick( "✶", "\uF255", "f" );
        case icon::melee:
            return pick( "⚔", "\U000F04E5", "/" );
        case icon::gun:
            return pick( "⌖", "\U000F0703", "=" );
        case icon::bow:
            return pick( "➶", "\U000F1841", ")" );
        case icon::style:
            return pick( "☯", "\U000F082C", "*" );
        case icon::walk:
            return pick( "•", "•", "." );
        case icon::run:
            return pick( "▶", "▶", ">" );
        case icon::crouch:
            return pick( "▼", "▼", "v" );
        case icon::prone:
            return pick( "━", "━", "-" );
        case icon::mana:
            return pick( "✦", "✦", "+" );
        case icon::compass:
            return pick( "⊕", "\U000F018B", "+" );
        case icon::fuel:
            return pick( "▤", "\U000F0298", "F" );
        case icon::battery:
            return pick( "↯", "\U000F0079", "B" );
        case icon::pain:
            return pick( "☹", "☹", "" );
        case icon::thirst:
            return pick( "☕", "☕", "" );
        case icon::hunger:
            return pick( "♨", "♨", "" );
        case icon::rest:
            return pick( "zz", "zz", "" );
        case icon::heat:
            return pick( "°", "°", "" );
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
    bool separator = false;
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

/// Columns the weather row needs for its current text, icon column included.
auto weather_row_width( const avatar &you, const std::string &icons ) -> int
{
    const auto underground = you.bub_pos().z() < 0;
    const auto icon_w = icons == "ascii" ? 0 :
                        std::max( utf8_width( glyph( icon::underground, icons ) ),
                                  utf8_width( glyph( weather_icon( get_weather().weather_id.str() ), icons ) ) );
    const auto prefix = icon_w > 0 ? icon_w + 1 : 0;
    const auto label = icons == "ascii" ? std::string( _( "Weather" ) ) + ": " : std::string();
    return prefix + utf8_width( label + weather_text( you, underground ) );
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
    if( compact_bars() ) {
        const auto light = get_light_level( character_funcs::fine_detail_vision_mod( you ) );
        const auto wind = wind_text( you, icons == "ascii" );
        const auto label = icons == "ascii" ? std::string( _( "Weather" ) ) + ": " + description :
                           description;
        auto text = label;
        text += "  │  " + season_day_text() + " " + time_text( you );
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
    const auto clock = icons == "ascii" ? std::string() : std::string( "◷" );
    out.push_back( { .icon = clock, .icon_w = utf8_width( clock ), .icon_color = c_light_gray,
                     .text = season_day_text() + " " + time_text( you ) + " " +
                             moon_phase_name( get_moon_phase( calendar::turn ) ),
                     .text_color = c_light_gray } );
    const auto light = get_light_level( character_funcs::fine_detail_vision_mod( you ) );
    const auto light_icon = icons == "ascii" ? std::string() : std::string( "⊙" );
    out.push_back( { .icon = light_icon, .icon_w = utf8_width( light_icon ), .icon_color = light.second,
                     .text = string_format( _( "Light: %s" ), light.first ), .text_color = light.second } );
    const auto wind = wind_text( you, icons == "ascii" );
    // Every other row owns an icon cell, so the wind row keeps an empty one to stay in column.
    const auto wind_icon = icons == "ascii" ? std::string() : std::string( " " );
    out.push_back( { .icon = wind_icon, .icon_w = utf8_width( wind_icon ), .icon_color = wind.color,
                     .text = string_format( _( "Wind: %s" ), wind.text ), .text_color = wind.color } );
    return out;
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
    const auto style = you.martial_arts_data->selected_style_name( you );
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
    if( compact_bars() ) {
        auto text = name + "  │  " + ( style.empty() ? _( "No style" ) : style ) + "  │  " +
                    stance_text;
        if( needs ) {
            const auto values = needs_status::read( you );
            text += string_format( _( "  │  Pain %s  Thirst %s  Hunger %s  Rest %s  Heat %s" ),
                                   values.pain.text, values.thirst.text, values.hunger.text,
                                   values.rest.text, values.heat.text );
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
    {
        const auto ic = icons == "ascii" ? std::string() : glyph( kind, icons );
        out.push_back( { .icon = ic, .icon_w = utf8_width( ic ), .icon_color = c_light_cyan,
                         .text = name, .text_color = c_light_gray, .label = _( "Weapon" ) } );
    }
    {
        const auto ic = icons == "ascii" ? std::string() : glyph( icon::style, icons );
        out.push_back( { .icon = ic, .icon_w = utf8_width( ic ), .icon_color = c_light_blue,
                         .text = style.empty() ? _( "No style" ) : style, .text_color = c_light_gray,
                         .label = _( "Style" ) } );
    }
    {
        const auto ic = icons == "ascii" ? std::string() : glyph( stance_icon, icons );
        out.push_back( { .icon = ic, .icon_w = utf8_width( ic ), .icon_color = stance_color,
                         .text = stance_text, .text_color = stance_color, .label = _( "Stance" ) } );
    }
    if( needs ) {
        out.push_back( { .icon = "", .icon_w = 0, .icon_color = c_dark_gray,
                         .text = "", .text_color = c_dark_gray, .separator = true } );
        const auto values = needs_status::read( you );
        const auto add = [&]( const icon symbol, const char *label, const needs_status::reading & value ) {
            const auto ic = icons == "ascii" ? std::string() : glyph( symbol, icons );
            out.push_back( { .icon = ic, .icon_w = utf8_width( ic ), .icon_color = value.color,
                             .text = value.text, .text_color = value.color, .label = label } );
        };
        add( icon::pain, _( "Pain" ), values.pain );
        add( icon::thirst, _( "Thirst" ), values.thirst );
        add( icon::hunger, _( "Hunger" ), values.hunger );
        add( icon::rest, _( "Rest" ), values.rest );
        add( icon::heat, _( "Heat" ), values.heat );
    }
    if( hud_boxes::mana_matters( you ) ) {
        const auto mana = hud_boxes::mana_reading( you );
        const auto ic = icons == "ascii" ? std::string() : glyph( icon::mana, icons );
        out.push_back( { .icon = ic, .icon_w = utf8_width( ic ), .icon_color = mana.color,
                         .text = mana.text, .text_color = mana.color, .label = _( "Mana" ) } );
    }
    return out;
}

/// Columns the one-row weather bar needs, icon column included.
auto weather_bar_width( const avatar &you, const std::string &icons ) -> int
{
    const auto lines = weather_lines( you, icons );
    const auto &line = lines.front();
    return line.icon_w + ( line.icon_w > 0 ? 1 : 0 ) + utf8_width( line.text );
}

/// Columns the one-row status bar needs, icon column included.
auto combat_bar_width( const avatar &you, const std::string &icons, bool needs ) -> int
{
    const auto lines = combat_lines( you, icons, needs );
    const auto &line = lines.front();
    return line.icon_w + ( line.icon_w > 0 ? 1 : 0 ) + utf8_width( line.text );
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
        if( entry.separator ) {
            auto bar = std::string();
            for( auto col = 0; col < inner; ++col ) {
                bar += frame.horizontal;
            }
            mvwprintz( w, row + point( 2, 0 ), c_dark_gray, bar );
        } else if( label_width > 0 ) {
            mvwprintz( w, row + point( 2, 0 ), entry.icon_color, entry.icon );
            const auto label_at = row + point( 2 + icon_width, 0 );
            mvwprintz( w, label_at, c_light_gray, entry.label );
            mvwprintz( w, label_at + point( label_width, 0 ), c_dark_gray, " | " );
            trim_and_print( w, label_at + point( label_width + 3, 0 ),
                            inner - icon_width - label_width - 3, entry.text_color, entry.text );
        } else {
            mvwprintz( w, row + point( 2, 0 ), entry.icon_color, entry.icon );
            const auto prefix = entry.icon_w > 0 ? entry.icon_w + 1 : 0;
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
    bool mana;
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
                candidate.label_width = input.label_width;
                candidate.icon_width = input.ascii ? 0 : 3;
                candidate.inner = candidate.icon_width + input.label_width + 3 + ( roomy ? 21 : 17 );
                candidate.rows = 9 + input.mana;
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
        if( !accepted && index == 1 ) {
            candidate.rows = 3 + input.mana;
            accepted = fits();
        }
        if( accepted ) {
            result.boxes[index] = candidate;
            used[corner_index] += candidate.height();
            if( index == 1 ) {
                result.needs = input.bars || candidate.rows == 9 + input.mana;
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
             _( "Weapon" ), _( "Style" ), _( "Stance" ), _( "Pain" ),
             _( "Thirst" ), _( "Hunger" ), _( "Rest" ), _( "Heat" ), _( "Mana" )
         } ) {
        label_width = std::max( label_width, utf8_width( label ) );
    }
    auto vehicle = corners[2] == "off" ? vehicle_state{} :
                   current_vehicle( you );
    const auto icons = get_option<std::string>( "HUD_ICONS" );
    const auto ascii = icons == "ascii";
    const auto bars = compact_bars();
    // Size every weather row, not only the date row; the description can outgrow it.
    const auto weather_inner = corners[0] == "off" ? 0 :
                               bars ? weather_bar_width( you, icons ) :
                               std::max( { 38,
                                           utf8_width( season_day_text() ) + utf8_width( time_text( you ) ) +
                                           utf8_width( moon_phase_name( get_moon_phase( calendar::turn ) ) ) + 2 +
                                           ( ascii ? 0 : 2 ),
                                           weather_row_width( you, icons ) } );
    // The needs summary is the widest part of the status bar, and the sidebar keeps its own
    // needs panel, so the bar drops it rather than being pushed off the map.
    auto bar_needs = false;
    auto combat_inner = 0;
    if( corners[1] != "off" && bars ) {
        const auto full = combat_bar_width( you, icons, true );
        bar_needs = full + 4 <= width;
        combat_inner = bar_needs ? full : combat_bar_width( you, icons, false );
    }
    auto geometry = calculate_layout( {
        .width = width, .height = height, .corners = corners,
        .label_width = label_width, .weather_inner = weather_inner,
        .combat_inner = combat_inner, .ascii = ascii, .bars = bars,
        .mana = corners[1] != "off" && hud_boxes::mana_matters( you ), .vehicle_rows = vehicle.rows
    } );
    geometry.bars = bars;
    geometry.bar_needs = bar_needs;
    return { .geometry = geometry, .vehicle = std::move( vehicle ) };
}

} // namespace

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
    return !compact_bars() && plan_for( get_avatar() ).geometry.boxes[0].rows > 0;
}

auto weather_box_shows_environment() -> bool
{
    return weather_box_shown();
}

auto combat_box_shown() -> bool
{
    return !compact_bars() && plan_for( get_avatar() ).geometry.boxes[1].rows > 0;
}

auto status_box_shows_needs() -> bool
{
    return !compact_bars() && plan_for( get_avatar() ).geometry.needs;
}

auto combat_box_shows_mana( const Character &you ) -> bool
{
    return !compact_bars() && combat_box_shown() && mana_matters( you );
}

auto vehicle_box_shown() -> bool
{
    return plan_for( get_avatar() ).geometry.boxes[2].rows > 0;
}

auto draw( const avatar &you, const catacurses::window &w ) -> void
{
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

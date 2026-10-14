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

/// The weather box redraws every frame; scanning the whole inventory once per turn is enough.
auto has_thermometer( const avatar &you ) -> bool
{
    static auto checked_on = std::optional<time_point>();
    static auto cached = false;
    if( checked_on != calendar::turn ) {
        cached = you.has_item_with_flag( flag_THERMOMETER ) ||
                 you.has_enchantment_flag( enchantment_flag_id( "THERMOMETER" ) );
        checked_on = calendar::turn;
    }
    return cached;
}

enum class icon {
    sun, moon, cloud, rain, storm, snow, strange, underground, fists, melee, gun, bow, style,
    walk, run, crouch, prone, mana, compass, fuel, battery
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
};

auto time_text( const avatar &you ) -> std::string
{
    if( you.has_watch() ) {
        return to_string_time_of_day( calendar::turn );
    }
    const auto hour = hour_of_day<int>( calendar::turn );
    return hour < 5 ? _( "night" ) : hour < 8 ? _( "dawn" ) : hour < 12 ? _( "morning" ) :
           hour < 14 ? _( "noon" ) : hour < 18 ? _( "afternoon" ) : hour < 21 ? _( "evening" ) : _( "night" );
}

struct wind_info {
    std::string text;
    nc_color color;
};

/// Local wind as the Wind panel shows it: description plus arrow, colored by strength.
auto wind_text( const avatar &you ) -> wind_info
{
    const oter_id &cur_om_ter = ACTIVE_OVERMAP_BUFFER.ter( you.abs_omt_pos() );
    const weather_manager &weather = get_weather();
    const double windpower = get_local_windpower( weather.windspeed, cur_om_ter,
                             you.abs_pos(), weather.winddirection,
                             weather::is_sheltered( get_map(), you.bub_pos() ) );
    return { get_wind_desc( windpower ) + " " + get_wind_arrow( weather.winddirection ),
             get_wind_color( windpower ) };
}

auto weather_lines( const avatar &you, const std::string &icons ) -> std::vector<line>
{
    auto out = std::vector<line>();
    const auto &w = get_weather();
    const auto underground = you.bub_pos().z() < 0;
    const auto first = underground ? glyph( icon::underground, icons )
                                   : glyph( weather_icon( w.weather_id.str() ), icons );
    const auto iw = utf8_width( first );
    if( underground ) {
        out.push_back( { .icon = std::move( first ), .icon_w = iw, .icon_color = c_light_gray,
                         .text = _( "Underground" ), .text_color = c_light_gray } );
    } else {
        out.push_back( { .icon = std::move( first ), .icon_w = iw, .icon_color = w.weather_id->color,
                         .text = w.weather_id->name.translated(), .text_color = w.weather_id->color } );
    }
    const auto indent = std::string( iw, ' ' );
    auto time_line = time_text( you );
    if( has_thermometer( you ) ) {
        time_line += "  " + print_temperature( w.get_temperature( you.abs_pos() ) );
    }
    out.push_back( { .icon = indent, .icon_w = iw, .icon_color = c_light_gray,
                     .text = time_line, .text_color = c_light_gray } );
    if( !hud_boxes::roomy() ) {
        return out;
    }
    out.push_back( { .icon = indent, .icon_w = iw, .icon_color = c_light_gray,
                     .text = string_format( _( "%s, day %d" ),
                                            calendar::name_season( season_of_year( calendar::turn ) ),
                                            day_of_season<int>( calendar::turn ) + 1 ),
                     .text_color = c_light_gray } );
    const auto light = get_light_level( character_funcs::fine_detail_vision_mod( you ) );
    out.push_back( { .icon = indent, .icon_w = iw, .icon_color = c_light_gray,
                     .text = string_format( _( "Light: %s" ), colorize( light.first, light.second ) ),
                     .text_color = c_light_gray } );
    out.push_back( { .icon = indent, .icon_w = iw, .icon_color = c_light_gray,
                     .text = string_format( _( "Moon: %s" ),
                                            moon_phase_name( get_moon_phase( calendar::turn ) ) ),
                     .text_color = c_light_gray } );
    const auto wind = wind_text( you );
    out.push_back( { .icon = indent, .icon_w = iw, .icon_color = c_light_gray,
                     .text = string_format( _( "Wind: %s" ), colorize( wind.text, wind.color ) ),
                     .text_color = c_light_gray } );
    return out;
}

auto combat_lines( const avatar &you, const std::string &icons ) -> std::vector<line>
{
    auto out = std::vector<line>();
    const auto &weapon = you.primary_weapon();
    auto kind = icon::fists;
    if( you.is_armed() ) {
        kind = !weapon.is_gun() ? icon::melee :
               weapon.gun_skill() == skill_id( "archery" ) ? icon::bow : icon::gun;
    }
    const auto name = you.is_armed() ? character_funcs::fmt_wielded_weapon( you ) : std::string(
                          _( "fists" ) );
    {
        const auto ic = glyph( kind, icons );
        const auto iw = utf8_width( ic );
        out.push_back( { .icon = std::move( ic ), .icon_w = iw, .icon_color = c_light_cyan,
                         .text = name, .text_color = c_light_gray } );
    }
    const auto style = you.martial_arts_data->selected_style_name( you );
    if( !style.empty() ) {
        const auto ic = glyph( icon::style, icons );
        const auto iw = utf8_width( ic );
        out.push_back( { .icon = std::move( ic ), .icon_w = iw, .icon_color = c_light_blue,
                         .text = style, .text_color = c_light_gray } );
    }
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
    {
        const auto ic = glyph( stance_icon, icons );
        const auto iw = utf8_width( ic );
        out.push_back( { .icon = std::move( ic ), .icon_w = iw, .icon_color = stance_color,
                         .text = stance_text, .text_color = stance_color } );
    }
    if( hud_boxes::roomy() && hud_boxes::mana_matters( you ) ) {
        const auto mana = hud_boxes::mana_reading( you );
        const auto ic = glyph( icon::mana, icons );
        const auto iw = utf8_width( ic );
        out.push_back( { .icon = std::move( ic ), .icon_w = iw, .icon_color = c_light_blue,
                         .text = string_format( _( "Mana: %s" ), colorize( mana.text, mana.color ) ),
                         .text_color = c_light_gray } );
    }
    return out;
}

auto vehicle_lines( const avatar &you, const std::string &icons ) -> std::vector<line>
{
    auto out = std::vector<line>();
    auto *veh = g->remoteveh();
    if( veh == nullptr && you.in_vehicle ) {
        veh = veh_pointer_or_null( get_map().veh_at( you.bub_pos() ) );
    }
    if( veh == nullptr ) {
        return out;
    }
    out.reserve( 7 );
    static const auto fuel_type_battery = itype_id( "battery" );
    static const auto fuel_type_muscle = itype_id( "muscle" );

    {
        const auto ic = glyph( icon::compass, icons );
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
        if( veh->has_part( "WING" ) ) {
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

    auto engine_fuel = std::optional<itype_id>();
    for( auto e = size_t{ 0 }; e < veh->engines.size(); ++e ) {
        if( veh->is_perpetual_type( e ) || veh->is_engine_type( e, fuel_type_muscle ) ) {
            continue;
        }
        const auto &fuel = veh->cpart( veh->engines[e] ).fuel_current();
        if( fuel.is_null() ) {
            continue;
        }
        if( !engine_fuel || veh->is_engine_on( e ) ) {
            engine_fuel = fuel;
        }
        if( veh->is_engine_on( e ) ) {
            break;
        }
    }
    const auto percentage = [&]( const itype_id & fuel ) {
        const auto capacity = veh->fuel_capacity( fuel );
        return capacity > 0 ? static_cast<int>(
                   static_cast<int64_t>( veh->fuel_left( fuel ) ) * 100 / capacity ) : 0;
    };
    if( engine_fuel && *engine_fuel != fuel_type_battery ) {
        const auto percent = percentage( *engine_fuel );
        const auto ic = glyph( icon::fuel, icons );
        const auto iw = utf8_width( ic );
        out.push_back( { .icon = std::move( ic ), .icon_w = iw, .icon_color = c_light_gray,
                         .text = string_format( _( "%s: %d%%" ), item::nname( *engine_fuel ), percent ),
                         .text_color = percent > 20 ? c_light_gray : percent > 5 ? c_yellow : c_red } );
    }
    if( veh->fuel_capacity( fuel_type_battery ) > 0 ) {
        const auto percent = percentage( fuel_type_battery );
        const auto color = percent > 20 ? c_light_cyan : percent > 5 ? c_yellow : c_red;
        const auto ic = glyph( icon::battery, icons );
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
};

auto draw_box( const catacurses::window &w, const box_spec &box ) -> void
{
    const auto &[at, inner, lines] = box;
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
        mvwprintz( w, row + point( 2, 0 ), lines[i].icon_color, lines[i].icon );
        const auto icon_w = lines[i].icon_w;
        trim_and_print( w, row + point( 3 + icon_w, 0 ), inner - icon_w - 1, lines[i].text_color,
                        lines[i].text );
        mvwprintz( w, row + point( inner + 3, 0 ), c_dark_gray, frame.vertical );
    }
    mvwprintz( w, at + point( 0, lines.size() + 1 ), c_dark_gray, bot_bar );
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

auto roomy() -> bool
{
    return g->w_terrain && getmaxx( g->w_terrain ) >= 54;
}

auto weather_box_shown() -> bool
{
    return !is_draw_tiles_mode() && get_option<std::string>( "HUD_WEATHER_BOX" ) != "off";
}

auto weather_box_shows_environment() -> bool
{
    return weather_box_shown() && roomy();
}

auto combat_box_shown() -> bool
{
    return !is_draw_tiles_mode() && get_option<std::string>( "HUD_COMBAT_BOX" ) != "off";
}

auto combat_box_shows_mana( const Character &you ) -> bool
{
    return combat_box_shown() && roomy() && mana_matters( you );
}

auto vehicle_box_shown() -> bool
{
    if( is_draw_tiles_mode() ) {
        return false;
    }
    const auto corner = get_option<std::string>( "HUD_VEHICLE_BOX" );
    if( corner == "off" ) {
        return false;
    }
    const auto &you = get_avatar();
    return g->remoteveh() != nullptr || you.in_vehicle;
}

auto draw( const avatar &you, const catacurses::window &w ) -> void
{
    struct box {
        std::string corner;
        std::vector<line> lines;
    };
    auto boxes = std::vector<box>();
    boxes.reserve( 3 );
    // Read once per frame; the boxes themselves draw the same icons.
    const auto icons = get_option<std::string>( "HUD_ICONS" );
    if( const auto corner = get_option<std::string>( "HUD_WEATHER_BOX" ); corner != "off" ) {
        boxes.push_back( { corner, weather_lines( you, icons ) } );
    }
    if( const auto corner = get_option<std::string>( "HUD_COMBAT_BOX" ); corner != "off" ) {
        boxes.push_back( { corner, combat_lines( you, icons ) } );
    }
    if( const auto corner = get_option<std::string>( "HUD_VEHICLE_BOX" ); corner != "off" ) {
        if( g->remoteveh() != nullptr || you.in_vehicle ) {
            auto lines = vehicle_lines( you, icons );
            if( !lines.empty() ) {
                boxes.push_back( { .corner = corner, .lines = std::move( lines ) } );
            }
        }
    }
    const auto width = getmaxx( w );
    const auto height = getmaxy( w );
    // Boxes in the same corner stack away from it. The option only ever holds one
    // of these four names, so fixed storage replaces a std::map.
    constexpr std::array<const char *, 4> corner_names = { "top_left", "top_right", "bottom_left", "bottom_right" };
    auto corner_used = std::array<int, 4>{ 0, 0, 0, 0 };
    for( const auto &b : boxes ) {
        auto inner = 0;
        for( const auto &l : b.lines ) {
            inner = std::max( inner, l.icon_w + 1 + utf8_width( l.text, true ) );
        }
        inner = std::min( inner, std::max( 8, width / 2 ) );
        const auto box_w = inner + 4;
        const auto box_h = static_cast<int>( b.lines.size() ) + 2;
        const auto right = b.corner.ends_with( "right" );
        const auto bottom = b.corner.starts_with( "bottom" );
        const auto corner = std::ranges::find( corner_names, b.corner );
        if( corner == corner_names.end() ) {
            continue;
        }
        auto &used = corner_used[static_cast<size_t>( corner - corner_names.begin() )];
        if( used + box_h > height || box_w > width ) {
            continue;
        }
        const auto x = right ? width - box_w : 0;
        const auto y = bottom ? height - used - box_h : used;
        draw_box( w, box_spec{ .at = point( x, y ), .inner = inner, .lines = b.lines } );
        used += box_h;
    }
}

} // namespace hud_boxes

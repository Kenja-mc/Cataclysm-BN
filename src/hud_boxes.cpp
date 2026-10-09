#include "hud_boxes.h"

#include <algorithm>
#include <map>
#include <string>
#include <vector>

#include "avatar.h"
#include "calendar.h"
#include "catacharset.h"
#include "character_functions.h"
#include "character_martial_arts.h"
#include "color.h"
#include "cursesdef.h"
#include "flag.h"
#include "item.h"
#include "options.h"
#include "output.h"
#include "string_formatter.h"
#include "translations.h"
#include "weather/weather.h"

namespace
{

enum class icon {
    sun, moon, cloud, rain, storm, snow, strange, underground, fists, melee, gun, bow, style
};

/// One glyph per icon for each icon set. Nerd Font glyphs are Material Design icons (the fist is Font Awesome).
auto glyph( const icon i ) -> std::string
{
    const auto style = get_option<std::string>( "HUD_ICONS" );
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

auto weather_lines( const avatar &you ) -> std::vector<line>
{
    auto out = std::vector<line>();
    const auto &w = get_weather();
    if( you.bub_pos().z() < 0 ) {
        out.push_back( { glyph( icon::underground ), c_light_gray, _( "Underground" ), c_light_gray } );
    } else {
        out.push_back( { glyph( weather_icon( w.weather_id.str() ) ), w.weather_id->color,
                         w.weather_id->name.translated(), w.weather_id->color } );
    }
    auto second = time_text( you );
    if( you.has_item_with_flag( flag_THERMOMETER ) ||
        you.has_enchantment_flag( enchantment_flag_id( "THERMOMETER" ) ) ) {
        second += "  " + print_temperature( w.get_temperature( you.abs_pos() ) );
    }
    out.push_back( { std::string( utf8_width( out.front().icon ), ' ' ), c_light_gray, second, c_light_gray } );
    return out;
}

auto combat_lines( const avatar &you ) -> std::vector<line>
{
    auto out = std::vector<line>();
    const auto &weapon = you.primary_weapon();
    auto kind = icon::fists;
    if( you.is_armed() ) {
        kind = !weapon.is_gun() ? icon::melee :
               weapon.gun_skill() == skill_id( "archery" ) ? icon::bow : icon::gun;
    }
    const auto name = you.is_armed() ? character_funcs::fmt_wielded_weapon( you ) : std::string( _( "fists" ) );
    out.push_back( { glyph( kind ), c_light_cyan, remove_color_tags( name ), c_white } );
    const auto style = you.martial_arts_data->selected_style_name( you );
    if( !style.empty() ) {
        out.push_back( { glyph( icon::style ), c_light_blue, style, c_light_gray } );
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
    const auto rounded = get_option<bool>( "UI_ROUNDED_BORDERS" );
    const auto bar = [&]( const char *l, const char *r ) {
        auto s = std::string( l );
        for( int i = 0; i < inner + 2; i++ ) {
            s += "─";
        }
        return s + r;
    };
    mvwprintz( w, at, c_dark_gray, bar( rounded ? "╭" : "┌", rounded ? "╮" : "┐" ) );
    for( size_t i = 0; i < lines.size(); i++ ) {
        const auto row = at + point( 0, i + 1 );
        mvwprintz( w, row, c_dark_gray, "│" );
        mvwprintz( w, row + point( 1, 0 ), c_black, std::string( inner + 2, ' ' ) );
        mvwprintz( w, row + point( 2, 0 ), lines[i].icon_color, lines[i].icon );
        const auto icon_w = utf8_width( lines[i].icon );
        trim_and_print( w, row + point( 3 + icon_w, 0 ), inner - icon_w - 1, lines[i].text_color, lines[i].text );
        mvwprintz( w, row + point( inner + 3, 0 ), c_dark_gray, "│" );
    }
    mvwprintz( w, at + point( 0, lines.size() + 1 ), c_dark_gray, bar( rounded ? "╰" : "└", rounded ? "╯" : "┘" ) );
}

} // namespace

namespace hud_boxes
{

auto draw( const avatar &you, const catacurses::window &w ) -> void
{
    struct box {
        std::string corner;
        std::vector<line> lines;
    };
    auto boxes = std::vector<box>();
    if( const auto corner = get_option<std::string>( "HUD_WEATHER_BOX" ); corner != "off" ) {
        boxes.push_back( { corner, weather_lines( you ) } );
    }
    if( const auto corner = get_option<std::string>( "HUD_COMBAT_BOX" ); corner != "off" ) {
        boxes.push_back( { corner, combat_lines( you ) } );
    }
    const auto width = getmaxx( w );
    const auto height = getmaxy( w );
    // Boxes in the same corner stack away from it.
    auto top = std::map<std::string, int>();
    for( const auto &b : boxes ) {
        auto inner = 0;
        for( const auto &l : b.lines ) {
            inner = std::max( inner, utf8_width( l.icon ) + 1 + utf8_width( l.text ) );
        }
        inner = std::min( inner, std::max( 8, width / 3 ) );
        const auto box_w = inner + 4;
        const auto box_h = static_cast<int>( b.lines.size() ) + 2;
        const auto right = b.corner.ends_with( "right" );
        const auto bottom = b.corner.starts_with( "bottom" );
        auto &used = top[b.corner];
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

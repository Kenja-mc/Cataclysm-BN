#include "driving_dashboard.h"

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <optional>
#include <string>
#include <utility>

#include "avatar.h"
#include "catacharset.h"
#include "game.h"
#include "hud_windows.h"
#include "icon_font.h"
#include "item.h"
#include "options.h"
#include "string_formatter.h"
#include "translations.h"
#include "units_utility.h"
#include "vehicle/vehicle.h"
#include "vehicle/vehicle_part.h"
#include "vehicle/vpart_position.h"

namespace driving_dashboard
{

namespace
{

/// Instrument labels share this column so every value starts on the same cell.
constexpr auto label_column = 8;
/// A short bar reads in a terminal and still shows a direction of change without colour.
constexpr auto bar_cells = 6;
const auto fuel_type_muscle = itype_id( "muscle" );
const auto fuel_type_battery = itype_id( "battery" );

auto padded_label( const std::string &text ) -> std::string
{
    auto out = utf8_truncate( text, label_column );
    out.append( static_cast<size_t>( label_column - utf8_width( out ) ), ' ' );
    return out;
}

/// `#####-` for a value out of a scale.  The fill is a glyph, not a colour, so the reading
/// survives a monochrome terminal.
auto bar( const int value, const int scale ) -> std::string
{
    const auto filled = scale > 0 ?
                        std::clamp( value * bar_cells / scale, 0, bar_cells ) : 0;
    auto out = std::string( static_cast<size_t>( bar_cells ), '-' );
    std::ranges::fill_n( out.begin(), filled, '#' );
    return out;
}

struct controlled {
    vehicle *veh = nullptr;
    bool remote = false;
};

auto controlled_vehicle( const avatar &you ) -> controlled
{
    auto out = controlled{ .veh = g->remoteveh() };
    if( out.veh != nullptr ) {
        out.remote = true;
        return out;
    }
    if( you.in_vehicle ) {
        out.veh = veh_pointer_or_null( get_map().veh_at( you.bub_pos() ) );
    }
    return out;
}

/// The fuel of a running engine, else the first engine fuel a driver would watch.  This mirrors
/// the compact readout's choice so both presentations name the same tank.
auto engine_fuel( vehicle &veh ) -> std::optional<itype_id>
{
    auto out = std::optional<itype_id>();
    for( auto e = size_t{ 0 }; e < veh.engines.size(); ++e ) {
        if( veh.is_perpetual_type( e ) || veh.is_engine_type( e, fuel_type_muscle ) ) {
            continue;
        }
        const auto &fuel = veh.cpart( veh.engines[e] ).fuel_current();
        if( fuel.is_null() ) {
            continue;
        }
        if( !out || veh.is_engine_on( e ) ) {
            out = fuel;
        }
        if( veh.is_engine_on( e ) ) {
            break;
        }
    }
    return out;
}

auto percentage( const vehicle &veh, const itype_id &fuel ) -> int
{
    const auto capacity = veh.fuel_capacity( fuel );
    if( capacity <= 0 ) {
        return 0;
    }
    return static_cast<int>( static_cast<int64_t>( veh.fuel_left( fuel ) ) * 100 / capacity );
}

auto fuel_note( const int percent ) -> std::string
{
    if( percent <= 0 ) {
        return std::string( " " ) + _( "empty" );
    }
    if( percent <= 5 ) {
        return std::string( " " ) + _( "low" ) + "!";
    }
    if( percent <= 20 ) {
        return std::string( " " ) + _( "low" );
    }
    return {};
}

auto fuel_color( const int percent ) -> nc_color
{
    return percent > 20 ? c_light_gray : percent > 5 ? c_yellow : c_red;
}

/// One scale for both the row colour and the text marker, so a coloured warning always has a cue.
enum class strain_level {
    none,
    light,
    heavy,
    critical
};

auto strain_level_of( const float strain ) -> strain_level
{
    if( strain <= 0.0f ) {
        return strain_level::none;
    }
    if( strain <= 0.2f ) {
        return strain_level::light;
    }
    if( strain <= 0.4f ) {
        return strain_level::heavy;
    }
    return strain_level::critical;
}

auto strain_marker( const strain_level level ) -> std::string
{
    switch( level ) {
        case strain_level::none:
            return {};
        case strain_level::light:
            return " !";
        case strain_level::heavy:
            return " !!";
        case strain_level::critical:
            return " !!!";
    }
    return {};
}

auto speed_color( const strain_level level ) -> nc_color
{
    switch( level ) {
        case strain_level::none:
            return c_light_blue;
        case strain_level::light:
            return c_yellow;
        case strain_level::heavy:
            return c_light_red;
        case strain_level::critical:
            return c_red;
    }
    return c_light_blue;
}

auto engine_color( const bool running, const strain_level level ) -> nc_color
{
    if( !running ) {
        return c_light_gray;
    }
    switch( level ) {
        case strain_level::none:
            return c_light_green;
        case strain_level::light:
            return c_yellow;
        case strain_level::heavy:
            return c_light_red;
        case strain_level::critical:
            return c_red;
    }
    return c_light_green;
}

auto battery_color( const int percent ) -> nc_color
{
    return percent > 20 ? c_light_cyan : percent > 5 ? c_yellow : c_red;
}

/// Text-only rows still reserve the icon column so their values line up with the glyph rows.
auto text_row( std::string text, const nc_color color ) -> hud_windows::window_line
{
    return { .icon = {}, .icon_w = 0, .icon_color = color, .text = std::move( text ),
             .text_color = color, .label = {} };
}

auto icon_row( std::string icon, std::string text, const nc_color color )
-> hud_windows::window_line
{
    const auto icon_w = utf8_width( icon );
    return { .icon = std::move( icon ), .icon_w = icon_w, .icon_color = color,
             .text = std::move( text ), .text_color = color, .label = {} };
}

/// The compact readout's icon vocabulary, limited to the three instrument rows that have one.
enum class gauge {
    compass,
    fuel,
    battery
};

auto gauge_glyph( const gauge kind, const std::string &style ) -> std::string
{
    if( style == "ascii" ) {
        return {};
    }
    const auto nerd_glyph = [&]( const char *bundled, const char *mdi ) -> std::string {
        if( style != "nerd" ) {
            return {};
        }
        return icon_font::bundled ? std::string( bundled ) : std::string( mdi );
    };
    switch( kind ) {
        case gauge::compass: {
            const auto nerd = nerd_glyph( icon_font::compass, "\U000F018B" );
            return nerd.empty() ? std::string( "⊕" ) : nerd;
        }
        case gauge::fuel: {
            const auto nerd = nerd_glyph( icon_font::gas_station, "\U000F0298" );
            return nerd.empty() ? std::string( "▤" ) : nerd;
        }
        case gauge::battery: {
            const auto nerd = nerd_glyph( icon_font::battery, "\U000F0079" );
            return nerd.empty() ? std::string( "↯" ) : nerd;
        }
    }
    return {};
}

/// A fixed gutter for the glyph rows; the bundled font's copies are two cells wide.
auto icon_column( const std::string &style ) -> int
{
    if( style == "ascii" ) {
        return 0;
    }
    return style == "nerd" && icon_font::bundled ? 3 : 2;
}

auto fuel_row( vehicle &veh, const itype_id &fuel, const std::string &icons )
-> hud_windows::window_line
{
    const auto percent = percentage( veh, fuel );
    const auto electric = fuel == fuel_type_battery;
    return icon_row( gauge_glyph( electric ? gauge::battery : gauge::fuel, icons ),
                     string_format( "%s %s %d%%%s", padded_label( item::nname( fuel ) ),
                                    bar( percent, 100 ), percent, fuel_note( percent ) ),
                     electric ? battery_color( percent ) : fuel_color( percent ) );
}

/// Compass letters for the eight facings, in tileray's order (0 = east).  Not cached: the
/// language can change without restarting the game.
auto compass_letter( const int octant ) -> std::string
{
    switch( std::clamp( octant, 0, 7 ) ) {
        case 0:
            return pgettext( "compass direction", "E" );
        case 1:
            return pgettext( "compass direction", "SE" );
        case 2:
            return pgettext( "compass direction", "S" );
        case 3:
            return pgettext( "compass direction", "SW" );
        case 4:
            return pgettext( "compass direction", "W" );
        case 5:
            return pgettext( "compass direction", "NW" );
        case 6:
            return pgettext( "compass direction", "N" );
        default:
            return pgettext( "compass direction", "NE" );
    }
}

} // namespace

auto read( const avatar &you ) -> hud_windows::vehicle_reading
{
    auto out = hud_windows::vehicle_reading{};
    const auto state = controlled_vehicle( you );
    auto *const veh = state.veh;
    if( veh == nullptr ) {
        return out;
    }
    out.applicable = true;
    out.body.reserve( 8 );

    const auto units = velocity_units( VU_VEHICLE );
    const auto speed = static_cast<int>( convert_velocity( veh->velocity, VU_VEHICLE ) );
    const auto cruising = veh->cruise_on;
    const auto cruise = static_cast<int>( convert_velocity( veh->cruise_velocity, VU_VEHICLE ) );
    const auto heading = compass_letter( veh->face.dir8() );
    const auto icons = get_option<std::string>( "HUD_ICONS" );

    out.icon_width = icon_column( icons );

    // The title owns the speed and cardinal; the body shows the bar, azimuth, cruise and
    // engine/fuel state, so no reading is repeated and the title stays short.
    out.summary = string_format( "%d %s %s", speed, units, heading );

    if( state.remote ) {
        out.body.push_back( text_row( _( "Remote control" ), c_light_cyan ) );
    }

    // The bar fills toward the safe speed; above it the strain colour and marker start.
    // safe_velocity does not emit the debug message max_velocity does.
    const auto safe_speed = static_cast<int>(
                                convert_velocity( veh->safe_velocity( false ), VU_VEHICLE ) );
    const auto scale = std::max( std::abs( safe_speed ), 1 );
    const auto strain = strain_level_of( veh->strain() );
    out.body.push_back( text_row(
                            string_format( "%s %s", padded_label( _( "Speed" ) ),
                                           bar( std::abs( speed ), scale ) ),
                            speed_color( strain ) ) );

    out.body.push_back( text_row(
                            string_format( "%s %s", padded_label( _( "Cruise" ) ),
                                           cruising ? string_format( "%s %d %s", _( "On" ), cruise,
                                                   units ) : std::string( _( "Off" ) ) ),
                            cruising ? c_light_green : c_light_gray ) );

    out.body.push_back( icon_row(
                            gauge_glyph( gauge::compass, icons ),
                            string_format( "%s %s", padded_label( _( "Heading" ) ),
                                           veh->face.to_string_azimuth_from_north() ),
                            c_light_gray ) );

    // Every coloured strain state also has a marker: `!`, `!!` and `!!!` for its three levels.
    const auto engine_state = veh->engine_on ? _( "On" ) : _( "Off" );
    out.body.push_back( text_row(
                            string_format( "%s %s%s", padded_label( _( "Engine" ) ), engine_state,
                                           strain_marker( strain ) ),
                            engine_color( veh->engine_on, strain ) ) );

    const auto fuel = engine_fuel( *veh );
    if( fuel ) {
        out.body.push_back( fuel_row( *veh, *fuel, icons ) );
    }
    if( ( !fuel || *fuel != fuel_type_battery ) &&
        veh->fuel_capacity( fuel_type_battery ) > 0 ) {
        out.body.push_back( fuel_row( *veh, fuel_type_battery, icons ) );
    }

    if( veh->has_part( "WING" ) ) {
        const auto takeoff = veh->get_takeoff_speed();
        // Zero means the wings cannot lift this vehicle; reaching the number means lift.
        const auto enough = takeoff > 0 && speed >= takeoff;
        out.body.push_back( text_row(
                                string_format( "%s %d %s %s", padded_label( _( "Takeoff" ) ), takeoff,
                                               units, enough ? _( "lift" ) : _( "no lift" ) ),
                                enough ? c_light_green : c_light_red ) );
    }

    return out;
}

auto install() -> void
{
    hud_windows::set_vehicle_provider( read );
}

} // namespace driving_dashboard

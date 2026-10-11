#include <unordered_map>
#include "catacharset.h"
#include "color.h"
#include "panels_utility.h"
#include "translations.h"

std::string moon_phase_name( const moon_phase phase )
{
    switch( static_cast<int>( phase ) ) {
        case 0:
            return _( "New moon" );
        case 1:
            return _( "Waxing crescent" );
        case 2:
            return _( "Half moon" );
        case 3:
            return _( "Waxing gibbous" );
        case 4:
            return _( "Full moon" );
        case 5:
            return _( "Waning gibbous" );
        case 6:
            return _( "Half moon" );
        case 7:
            return _( "Waning crescent" );
        case 8:
            return _( "Dark moon" );
        default:
            return "";
    }
}

std::string trunc_ellipse( const std::string &input, unsigned int trunc )
{
    if( utf8_width( input ) > static_cast<int>( trunc ) ) {
        return utf8_truncate( input, trunc - 1 ) + "…";
    }
    return input;
}

nc_color color_compare_base( int base, int value )
{
    if( base < value ) {
        return c_green;
    } else if( value < base ) {
        return c_red;
    } else {
        return c_white;
    }
}

std::string value_trimmed( int value, int maximum )
{
    if( value > maximum ) {
        return "++";
    } else {
        return std::to_string( value );
    }
}

nc_color focus_color( int focus )
{
    if( focus < 25 ) {
        return c_red;
    } else if( focus < 50 ) {
        return c_light_red;
    } else if( focus < 75 ) {
        return c_yellow;
    } else if( focus < 100 ) {
        return c_light_gray;
    } else if( focus < 125 ) {
        return c_white;
    } else {
        return c_green;
    }
}

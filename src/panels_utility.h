#pragma once

#include <string>
#include "calendar.h"
#include "color.h"

/// Translated name of the moon phase, as the sidebar shows it.
auto moon_phase_name( moon_phase phase ) -> std::string;

std::string trunc_ellipse( const std::string &input, unsigned int trunc );

nc_color color_compare_base( int base, int value );

std::string value_trimmed( int value, int maximum = 100 );

nc_color focus_color( int focus );



#pragma once

#include <string>

#include "color.h"

class avatar;

namespace needs_status
{

struct reading {
    std::string text;
    nc_color color;
};

struct readings {
    reading pain;
    reading thirst;
    reading hunger;
    reading rest;
    reading heat;
};

auto temperature( const avatar &you ) -> reading;
auto read( const avatar &you ) -> readings;

} // namespace needs_status

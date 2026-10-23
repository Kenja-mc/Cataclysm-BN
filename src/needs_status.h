#pragma once

#include <string>

#include "color.h"

class avatar;

namespace needs_status
{

/// Which side of comfortable a body temperature reading lies on.
enum class thermal {
    none,
    cold,
    hot
};

struct reading {
    std::string text;
    nc_color color;
    /// No action needed; compact displays leave it out.
    bool fine = true;
    /// Set for body temperature, so a HUD row can carry a matching icon.
    thermal side = thermal::none;
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

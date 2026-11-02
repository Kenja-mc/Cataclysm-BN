#pragma once

#include <string>
#include <vector>

#include "color.h"

namespace Messages
{

struct recent_line {
    std::string text;
    nc_color color = c_light_gray;
};

auto recent_lines( size_t count ) -> std::vector<recent_line>;

}

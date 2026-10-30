#pragma once

#include <string>
#include <vector>

#include "color.h"

namespace Messages
{

struct recent_line {
    std::string text;
    /// The colour the message log gives it now: its type colour while fresh, gray once old.
    nc_color color = c_light_gray;
};

/// The last `count` messages, oldest first, with repeat counts and log colours.
auto recent_lines( size_t count ) -> std::vector<recent_line>;

} // namespace Messages

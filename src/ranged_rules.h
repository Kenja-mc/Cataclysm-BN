#pragma once

#include "units.h"

struct ranged_bash_info;

namespace ranged_rules
{

constexpr double max_miss_degrees = 30.0;

auto cover_blocks_unaimed( const ranged_bash_info &info, bool roll, bool point_blank ) -> bool;

auto capped_miss_angle( units::angle dispersion ) -> units::angle;

}

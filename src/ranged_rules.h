#pragma once

#include "units.h"

struct ranged_bash_info;

/// Physical rules the shot and the aim preview must agree on.
namespace ranged_rules
{

constexpr double max_miss_degrees = 30.0;

/// Whether unaimed cover stops the shot. `roll` is the result of the cover's
/// `block_unaimed_chance` check; point-blank shots pass over cover below 100%.
auto cover_blocks_unaimed( const ranged_bash_info &info, bool roll, bool point_blank ) -> bool;

/// A miss turns by at most 30 degrees, however wide the dispersion.
auto capped_miss_angle( units::angle dispersion ) -> units::angle;

} // namespace ranged_rules

#include "ranged_rules.h"

#include <algorithm>

#include "map/mapdata.h"

namespace ranged_rules
{

auto cover_blocks_unaimed( const ranged_bash_info &info, const bool roll,
                           const bool point_blank ) -> bool
{
    return roll && !( info.block_unaimed_chance < 100_pct && point_blank );
}

auto capped_miss_angle( const units::angle dispersion ) -> units::angle
{
    return std::min( dispersion, units::from_degrees( max_miss_degrees ) );
}

} // namespace ranged_rules

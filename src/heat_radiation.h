#pragma once

#include "coordinates.h"

struct heat_radiation {
    int best_fire = 0;
    int temp_mod = 0;
};

auto get_heat_radiation_data( const tripoint_bub_ms &location ) -> heat_radiation;

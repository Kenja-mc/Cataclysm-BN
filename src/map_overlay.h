#pragma once

#include <string>
#include <vector>

#include "coordinates.h"

class avatar;

namespace map_overlay
{

enum class overlay_kind {
    sound_marker,
    reticle,
    known_lock,
    health_bar,
    shot_blocker,
    stray_tile,
    aim_label,
};

enum class sound_flavor {
    plain,
    talk,
    violent,
};

struct overlay {
    tripoint_bub_ms pos;
    overlay_kind kind = overlay_kind::sound_marker;
    int age = 0;
    int severity = 0;
    std::string label;
    int z_offset = 0;
    bool stale = false;
    sound_flavor flavor = sound_flavor::plain;
    int value = 0;
    int max_value = 0;
};

auto collect( const avatar &you ) -> std::vector<overlay>;
auto kind_name( overlay_kind kind ) -> std::string;

}

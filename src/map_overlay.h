#pragma once

#include <string>
#include <vector>

#include "coordinates.h"

class avatar;

/// Map overlays decided once, then drawn by each renderer.
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

/// The kind of event a sound marker stands for; the terminal renderer colors by it.
enum class sound_flavor {
    plain,
    talk,
    violent,
};

struct overlay {
    tripoint_bub_ms pos;
    overlay_kind kind = overlay_kind::sound_marker;
    int age = 0;
    /// Health percentage, locked door kind, or another kind-specific bucket.
    int severity = 0;
    std::string label;
    /// Tile levels between the marker and the view center; renderers pick the arrow.
    int z_offset = 0;
    /// Two turns old while the marker glyph aging option is on.
    bool stale = false;
    sound_flavor flavor = sound_flavor::plain;
    /// Current and maximum value of a health bar.
    int value = 0;
    int max_value = 0;
};

auto collect( const avatar &you ) -> std::vector<overlay>;
auto kind_name( overlay_kind kind ) -> std::string;

} // namespace map_overlay

#pragma once

#include <optional>
#include <string>
#include <vector>

#include "coordinates.h"

namespace shot_preview
{

struct mark {
    tripoint_bub_ms pos;
    int severity = 0;
    std::string label;
};

struct state {
    bool active = false;
    std::vector<tripoint_bub_ms> strays;
    std::optional<mark> blocker;
    std::optional<mark> aim_label;
};

auto set( state next ) -> void;
auto clear() -> void;
auto active() -> bool;
auto current() -> const state &; // *NOPAD*
auto label_at( const tripoint_bub_ms &p ) -> std::string;

}

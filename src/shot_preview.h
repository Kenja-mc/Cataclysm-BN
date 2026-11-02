#pragma once

#include <optional>
#include <string>
#include <vector>

#include "coordinates.h"

/// Map marks published by the aim window for the renderers and the state file.
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
/// The aim text shown beside @p p, or an empty string.
auto label_at( const tripoint_bub_ms &p ) -> std::string;

} // namespace shot_preview

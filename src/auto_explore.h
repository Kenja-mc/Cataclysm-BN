#pragma once

#include <cstddef>
#include <functional>
#include <optional>
#include <vector>

#include "coordinates.h"

class avatar;
class map;

namespace auto_explore
{

struct frontier_options {
    avatar &you;
    map &here;
    int max_dist = 60;
    std::function < auto( const tripoint_bub_ms & ) -> bool > is_known;
};

auto frontiers( const frontier_options &opts, size_t count ) -> std::vector<tripoint_bub_ms>;

auto nearest_frontier( const frontier_options &opts ) -> std::optional<tripoint_bub_ms>;

auto set_route_to_frontier( const frontier_options &opts ) -> bool;

auto handle( avatar &you ) -> void;

}

#pragma once

#include <string>
#include <vector>

#include "coordinates.h"

class avatar;
class input_context;
class map;
struct input_event;

namespace global_search
{

struct target {
    enum class kind {
        control,
        creature,
        sighted,
        remembered
    };

    kind type = kind::control;
    std::string ident;
    std::string label;
    std::string detail;
    tripoint_bub_ms pos;
    int distance = 0;
    bool selectable = false;
    std::string match_text;
};

auto opens_here( const input_event &evt, const input_context &origin ) -> bool;

auto run( const input_context &origin ) -> std::string;

auto focus( const target &what ) -> bool;

auto map_targets( const avatar &you, map &here ) -> std::vector<target>;

}

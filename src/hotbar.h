#pragma once

#include <string>

#include "color.h"

class avatar;
class item;

namespace hotbar
{

constexpr auto slots = 6;

struct slot_view {
    bool assigned = false;
    std::string symbol;
    nc_color color = c_light_gray;
    std::string name;
    int count = 0;
    bool wielded = false;
};

auto view( const avatar &you, int slot ) -> slot_view;

auto use( avatar &you, int slot ) -> void;
auto assign( avatar &you ) -> void;
auto use_item( avatar &you, item *loc ) -> void;

}

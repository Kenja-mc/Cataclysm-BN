#pragma once

#include <functional>
#include <string>
#include <utility>
#include <vector>

#include "color.h"
#include "point.h"

class avatar;
namespace catacurses
{
class window;
}

namespace hud_windows
{

struct state {
    point pos = point_zero;
    bool placed = false;
    bool collapsed = false;
    bool visible = true;
    int order = 0;
};

struct window_line {
    std::string icon;
    int icon_w;
    nc_color icon_color;
    std::string text;
    nc_color text_color;
    std::string label;
};

struct vehicle_reading {
    bool applicable = false;
    std::string summary;
    std::vector<window_line> body;
    int icon_width = 0;
};

using vehicle_provider = std::function<vehicle_reading( const avatar & )>;

auto set_vehicle_provider( vehicle_provider provider ) -> void;

auto active() -> bool;

auto draw( const avatar &you, const catacurses::window &w ) -> void;

auto clicked( avatar &you, const catacurses::window &w, const point &map_cell ) -> bool;
auto secondary_clicked( avatar &you, const catacurses::window &w, const point &map_cell ) -> bool;
auto pointer_moved( avatar &you, const catacurses::window &w, const point &map_cell ) -> bool;
auto release() -> void;

auto entries() -> std::vector<std::pair<std::string, std::string>>;
auto visible( const avatar &you, const std::string &id ) -> bool;
auto shown( const std::string &id ) -> bool;
auto toggle( avatar &you, const std::string &id ) -> void;
auto raise( avatar &you, const std::string &id ) -> void;

}

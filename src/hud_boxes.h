#pragma once

#include <string>
#include <vector>

#include "color.h"

class avatar;
class Character;

namespace catacurses
{
class window;
}

namespace hud_boxes
{

struct mana_text {
    std::string text;
    nc_color color;
};

auto draw( const avatar &you, const catacurses::window &w ) -> void;

auto mana_matters( const Character &you ) -> bool;
auto mana_reading( const Character &you ) -> mana_text;
auto weather_box_shown() -> bool;
auto weather_box_shows_environment() -> bool;
auto combat_box_shown() -> bool;
auto status_box_shows_needs() -> bool;
auto combat_box_shows_mana( const Character &you ) -> bool;

auto vehicle_box_shown() -> bool;

struct vehicle_row {
    std::string text;
    nc_color color;
};
auto vehicle_rows( const avatar &you ) -> std::vector<vehicle_row>;

}

#pragma once

#include <string>

#include "color.h"

class avatar;
class Character;

namespace catacurses
{
class window;
} // namespace catacurses

/// Visibility checks include fit, not just option values.
namespace hud_boxes
{

struct mana_text {
    std::string text;
    nc_color color;
};

auto draw( const avatar &you, const catacurses::window &w ) -> void;

/// Show requested/spent mana, or mana used by known spells.
auto mana_matters( const Character &you ) -> bool;
/// current/max; "--" without a mana pool.
auto mana_reading( const Character &you ) -> mana_text;
auto weather_box_shown() -> bool;
auto weather_box_shows_environment() -> bool;
auto combat_box_shown() -> bool;
auto status_box_shows_needs() -> bool;
auto combat_box_shows_mana( const Character &you ) -> bool;

auto vehicle_box_shown() -> bool;

} // namespace hud_boxes

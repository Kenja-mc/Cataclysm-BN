#pragma once

#include <string>

#include "color.h"

class avatar;
class Character;

namespace catacurses
{
class window;
} // namespace catacurses

/// Small boxes drawn in a corner of the map: the weather and what you fight with.
/// Each has its own corner option (or off), and icons come in Unicode, Nerd Font or ASCII.
namespace hud_boxes
{

struct mana_text {
    std::string text;
    nc_color color;
};

auto draw( const avatar &you, const catacurses::window &w ) -> void;

/// Whether mana is worth showing: a mod asks for it, it is not full, or a known spell costs mana.
auto mana_matters( const Character &you ) -> bool;
/// "current/max", colored by how much is left; "--" without a mana pool.
auto mana_reading( const Character &you ) -> mana_text;
/// Whether the map is wide enough for the boxes' longer lines; narrow maps keep them short.
auto roomy() -> bool;
/// The weather box is on screen with the weather and time, so the sidebar leaves them out.
auto weather_box_shown() -> bool;
/// The weather box lists the season, light, moon and wind, so the sidebar leaves them out.
auto weather_box_shows_environment() -> bool;
/// The weapon box is on screen, so the sidebar leaves out the Weapon panel.
auto combat_box_shown() -> bool;
/// The weapon box carries the mana line, so the sidebar Mana panel steps aside.
auto combat_box_shows_mana( const Character &you ) -> bool;

/// The vehicle box is on screen, so the sidebar Vehicle panel steps aside.
auto vehicle_box_shown() -> bool;

} // namespace hud_boxes

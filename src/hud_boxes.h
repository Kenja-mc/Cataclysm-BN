#pragma once

class avatar;

namespace catacurses
{
class window;
} // namespace catacurses

/// Small boxes drawn in a corner of the map: the weather and what you fight with.
/// Each has its own corner option (or off), and icons come in Unicode, Nerd Font or ASCII.
namespace hud_boxes
{

auto draw( const avatar &you, const catacurses::window &w ) -> void;

} // namespace hud_boxes

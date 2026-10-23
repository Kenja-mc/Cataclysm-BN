#pragma once

class avatar;
namespace catacurses
{
class window;
} // namespace catacurses

namespace hud_sidebar
{
enum class section { weather, character, needs, vehicle };

auto active() -> bool;
auto height( section content ) -> int;
auto draw( avatar &you, const catacurses::window &w, section content ) -> void;
} // namespace hud_sidebar

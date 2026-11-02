#pragma once

class avatar;

namespace catacurses
{
class window;
}

auto draw_keyhints( const avatar &you, const catacurses::window &w ) -> void;

auto draw_menu_keyhints() -> void;

auto show_welcome_once() -> void;

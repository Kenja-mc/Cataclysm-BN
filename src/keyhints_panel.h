#pragma once

class avatar;

namespace catacurses
{
class window;
} // namespace catacurses

/// Sidebar strip listing the most used actions with their current key, lazygit-footer style.
auto draw_keyhints( const avatar &you, const catacurses::window &w ) -> void;

/// One-time welcome card listing the core keys; shown on the first new game.
auto show_welcome_once() -> void;

#pragma once

class avatar;

namespace catacurses
{
class window;
} // namespace catacurses

/// Sidebar strip listing the most used actions with their current key, lazygit-footer style.
auto draw_keyhints( const avatar &you, const catacurses::window &w ) -> void;

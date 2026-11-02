#pragma once

class avatar;

namespace catacurses
{
class window;
}

namespace body_panel
{

auto draw( avatar &you, const catacurses::window &w ) -> void;
auto show_details( avatar &you ) -> void;

}

#pragma once

class avatar;

namespace catacurses
{
class window;
} // namespace catacurses

/// Project Zomboid style health view: a small body figure in the sidebar coloured by limb health,
/// with wounds listed beside it, and a key that opens the full per-limb breakdown.
namespace body_panel
{

auto draw( avatar &you, const catacurses::window &w ) -> void;
auto show_details( avatar &you ) -> void;

} // namespace body_panel

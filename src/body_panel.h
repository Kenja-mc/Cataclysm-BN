#pragma once

class avatar;

namespace catacurses
{
class window;
} // namespace catacurses

/// Project Zomboid style health view: the sidebar lists every hurt limb and what is wrong with
/// it, and a key opens the full per-limb breakdown.
namespace body_panel
{

auto draw( avatar &you, const catacurses::window &w ) -> void;
auto show_details( avatar &you ) -> void;

} // namespace body_panel

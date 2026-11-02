#pragma once

#include "hud_windows.h"

class avatar;

namespace driving_dashboard
{

/// Expanded instruments for Fusion and the floating vehicle window.
auto read( const avatar &you ) -> hud_windows::vehicle_reading;

/// Installs the floating-window reader; its option is checked by the window.
auto install() -> void;

} // namespace driving_dashboard

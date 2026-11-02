#pragma once

#include "hud_windows.h"

class avatar;

namespace driving_dashboard
{

auto read( const avatar &you ) -> hud_windows::vehicle_reading;

auto install() -> void;

}

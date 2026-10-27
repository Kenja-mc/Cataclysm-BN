#pragma once

#include <string>
#include <vector>

#include "color.h"

class avatar;

/// The driving dashboard (issue #21): a Project Zomboid-inspired instrument cluster for the
/// floating HUD's vehicle window.  It replaces that window's reading only; the fixed sidebar
/// layouts keep the compact readout in hud_boxes.cpp.
namespace driving_dashboard
{

/// One body row of the floating vehicle window.
struct line {
    /// Leading glyph; empty for rows with no matching icon.  A fixed icon column keeps the
    /// text aligned across rows.
    std::string icon;
    nc_color icon_color = c_light_gray;
    std::string text;
    nc_color color = c_light_gray;
};

/// Everything the dashboard reads from the driven or remotely controlled vehicle.
struct reading {
    /// False on foot, when there is no dashboard and no vehicle window.
    bool applicable = false;
    /// Live state for the window's title row, so a collapsed window still reads.
    std::string summary;
    std::vector<line> body;
    /// Width of the icon column; zero in the text-only icon setting.
    int icon_width = 0;
};

/// Reads the current vehicle.  Callers that are not the floating HUD should use the compact
/// readout instead.
auto read( const avatar &you ) -> reading;

/// Installs the dashboard as the floating HUD's vehicle reading.  Fixed layouts and a turned-off
/// floating HUD keep the compact readout, because the provider is only consulted when the
/// floating HUD is active.
auto install() -> void;

} // namespace driving_dashboard

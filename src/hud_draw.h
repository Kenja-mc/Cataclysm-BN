#pragma once

#include <string>

#include "color.h"
#include "cursesdef.h"
#include "point.h"

/// Small drawing helpers shared by the fusion HUD's overlays and sidebar sections.
namespace hud_draw
{

/// The map area overlays cover, in standard-font cells; (0, 0) is its top-left cell.
struct canvas {
    point origin = point_zero;
    int width = 0;
    int height = 0;
};

struct rect {
    point at = point_zero;
    int width = 0;
    int height = 0;
};

namespace glyph
{
inline constexpr auto hp = "♥";
inline constexpr auto stamina = "⚡";
inline constexpr auto focus = "◎";
inline constexpr auto pain = "†";
inline constexpr auto thirst = "○";
inline constexpr auto hunger = "↓";
inline constexpr auto rest = "⏾";
inline constexpr auto heat = "▲";
inline constexpr auto weapon = "◆";
inline constexpr auto place = "⌂";
inline constexpr auto safe = "⚠";
inline constexpr auto log = "»";
inline constexpr auto dot = "·";
} // namespace glyph

namespace pal
{
inline auto border() -> nc_color { return c_dark_gray; }
inline auto text() -> nc_color { return c_light_gray; }
inline auto muted() -> nc_color { return c_dark_gray; }
inline auto title() -> nc_color { return c_white; }
inline auto heading() -> nc_color { return c_light_cyan; }
inline auto accent() -> nc_color { return c_yellow; }
inline auto danger() -> nc_color { return c_light_red; }
inline auto stamina() -> nc_color { return c_yellow; }
inline auto focus() -> nc_color { return c_light_cyan; }
inline auto thirst() -> nc_color { return c_light_blue; }
inline auto hunger() -> nc_color { return c_brown; }
inline auto rest() -> nc_color { return c_pink; }
inline auto heat() -> nc_color { return c_light_red; }
} // namespace pal

/// Starts a frame of overlay windows; windows opened since the last frame are reused when their
/// geometry holds.
auto begin_frame() -> void;
/// Opens the next overlay window at `r` on the canvas, cleared.
auto panel( const canvas &area, const rect &r ) -> catacurses::window;
/// Queues every overlay window opened this frame for the screen, in opening order.
auto end_frame() -> void;

struct card_options {
    std::string title = {};
    /// Live state printed after the title, e.g. "2 wounded".
    std::string summary = {};
    nc_color summary_color = c_dark_gray;
};
/// Frames the whole window with rounded corners and a titled top edge.
auto card( const catacurses::window &w, const card_options &opts ) -> void;

struct rule_options {
    int y = 0;
    std::string title = {};
    std::string summary = {};
    nc_color summary_color = c_dark_gray;
};
/// A sidebar section rule across the window: "├─ BODY 2 wounded ─────".
auto rule( const catacurses::window &w, const rule_options &opts ) -> void;

struct bar_options {
    point at = point_zero;
    int width = 10;
    int value = 0;
    int max = 1;
    nc_color fill = c_light_green;
};
/// A gauge: full cells, one half cell for the remainder, empty cells after.
auto bar( const catacurses::window &w, const bar_options &opts ) -> void;

/// Prints text (colour tags allowed), clipped at the right edge; returns the next column.
auto text( const catacurses::window &w, point at, nc_color color, const std::string &s ) -> int;
/// Prints a muted " · " separator; returns the next column.
auto dot( const catacurses::window &w, point at ) -> int;
auto hline( const catacurses::window &w, point at, int width, nc_color color ) -> void;
auto vline( const catacurses::window &w, point at, int height, nc_color color ) -> void;
/// Display width of `s` without colour tags.
auto width( const std::string &s ) -> int;

} // namespace hud_draw

#pragma once

#include <string>

#include "color.h"
#include "cursesdef.h"
#include "point.h"

namespace hud_draw
{

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
inline constexpr auto check = "✓";
inline constexpr auto stamina = "⚡";
inline constexpr auto thirst = "○";
inline constexpr auto hunger = "↓";
inline constexpr auto rest = "⏾";
inline constexpr auto heat = "▲";
inline constexpr auto weapon = "◆";
inline constexpr auto safe = "⚠";
inline constexpr auto log = "»";
inline constexpr auto dot = "·";
}

namespace pal
{
inline auto border() -> nc_color { return c_dark_gray; }
inline auto text() -> nc_color { return c_light_gray; }
inline auto muted() -> nc_color { return c_light_gray; }
inline auto title() -> nc_color { return c_white; }
inline auto heading() -> nc_color { return c_light_cyan; }
inline auto accent() -> nc_color { return c_yellow; }
inline auto danger() -> nc_color { return c_light_red; }
inline auto stamina() -> nc_color { return c_yellow; }
inline auto thirst() -> nc_color { return c_light_blue; }
inline auto hunger() -> nc_color { return c_brown; }
inline auto rest() -> nc_color { return c_pink; }
inline auto heat() -> nc_color { return c_light_red; }
}

auto begin_frame() -> void;
auto panel( const canvas &area, const rect &r ) -> catacurses::window;
auto end_frame() -> void;

struct card_options {
    std::string title = {};
    std::string summary = {};
    nc_color summary_color = c_dark_gray;
};
auto card( const catacurses::window &w, const card_options &opts ) -> void;

struct rule_options {
    int y = 0;
    std::string title = {};
    std::string summary = {};
    nc_color summary_color = c_dark_gray;
};
auto rule( const catacurses::window &w, const rule_options &opts ) -> void;

struct bar_options {
    point at = point_zero;
    int width = 10;
    int value = 0;
    int max = 1;
    nc_color fill = c_light_green;
};
auto bar( const catacurses::window &w, const bar_options &opts ) -> void;

auto text( const catacurses::window &w, point at, nc_color color, const std::string &s ) -> int;
auto dot( const catacurses::window &w, point at ) -> int;
auto hline( const catacurses::window &w, point at, int width, nc_color color ) -> void;
auto vline( const catacurses::window &w, point at, int height, nc_color color ) -> void;
auto width( const std::string &s ) -> int;

}

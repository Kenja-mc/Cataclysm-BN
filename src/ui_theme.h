#pragma once

#include <array>
#include <cstdint>
#include <optional>
#include <string>

namespace ui_theme
{

struct rgb {
    std::uint8_t r = 0;
    std::uint8_t g = 0;
    std::uint8_t b = 0;
};

/// 16 colors in ANSI order: black red green brown blue magenta cyan gray, then their bright variants.
using palette = std::array<rgb, 16>;

/// Built-in palette for the UI_THEME option, or nullopt for themes that keep the existing colors.
auto builtin_palette( const std::string &theme ) -> std::optional<palette>;

/// True when the game should inherit the terminal's own colors and background.
auto inherits_terminal( const std::string &theme ) -> bool;

} // namespace ui_theme

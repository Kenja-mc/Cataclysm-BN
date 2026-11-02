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

using palette = std::array<rgb, 16>;

auto builtin_palette( const std::string &theme ) -> std::optional<palette>;

auto inherits_terminal( const std::string &theme ) -> bool;

}

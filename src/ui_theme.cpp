#include "ui_theme.h"

namespace ui_theme
{
namespace
{

constexpr auto hex( const std::uint32_t v ) -> rgb
{
    return { .r = static_cast<std::uint8_t>( v >> 16 ), .g = static_cast<std::uint8_t>( v >> 8 ), .b = static_cast<std::uint8_t>( v ) };
}

// Dark and bright variants are kept visibly distinct because the game encodes meaning in them.
constexpr auto tokyo_night = palette{ {
        hex( 0x1a1b26 ), hex( 0xc53b53 ), hex( 0x5f8a3a ), hex( 0xb5833a ),
        hex( 0x3d59a1 ), hex( 0x9d7cd8 ), hex( 0x0f94b0 ), hex( 0xa9b1d6 ),
        hex( 0x565f89 ), hex( 0xf7768e ), hex( 0x9ece6a ), hex( 0xe0af68 ),
        hex( 0x7aa2f7 ), hex( 0xbb9af7 ), hex( 0x7dcfff ), hex( 0xc0caf5 )
    } };

constexpr auto catppuccin = palette{ {
        hex( 0x1e1e2e ), hex( 0xd2476a ), hex( 0x5f9e57 ), hex( 0xc98b3c ),
        hex( 0x4f73c9 ), hex( 0xa66fd6 ), hex( 0x2c9a95 ), hex( 0xbac2de ),
        hex( 0x585b70 ), hex( 0xf38ba8 ), hex( 0xa6e3a1 ), hex( 0xf9e2af ),
        hex( 0x89b4fa ), hex( 0xcba6f7 ), hex( 0x94e2d5 ), hex( 0xcdd6f4 )
    } };

constexpr auto gruvbox = palette{ {
        hex( 0x282828 ), hex( 0xcc241d ), hex( 0x98971a ), hex( 0xd79921 ),
        hex( 0x458588 ), hex( 0xb16286 ), hex( 0x689d6a ), hex( 0xa89984 ),
        hex( 0x665c54 ), hex( 0xfb4934 ), hex( 0xb8bb26 ), hex( 0xfabd2f ),
        hex( 0x83a598 ), hex( 0xd3869b ), hex( 0x8ec07c ), hex( 0xebdbb2 )
    } };

constexpr auto everforest = palette{ {
        hex( 0x2d353b ), hex( 0xc4545a ), hex( 0x7f9a4f ), hex( 0xc59a52 ),
        hex( 0x4f7f8f ), hex( 0xb07a99 ), hex( 0x5f9a7f ), hex( 0x9da9a0 ),
        hex( 0x56635f ), hex( 0xe67e80 ), hex( 0xa7c080 ), hex( 0xdbbc7f ),
        hex( 0x7fbbb3 ), hex( 0xd699b6 ), hex( 0x83c092 ), hex( 0xd3c6aa )
    } };

} // namespace

auto builtin_palette( const std::string &theme ) -> std::optional<palette>
{
    if( theme == "tokyo_night" ) {
        return tokyo_night;
    } else if( theme == "catppuccin" ) {
        return catppuccin;
    } else if( theme == "gruvbox" ) {
        return gruvbox;
    } else if( theme == "everforest" ) {
        return everforest;
    }
    return std::nullopt;
}

auto inherits_terminal( const std::string &theme ) -> bool { return theme == "terminal"; }

} // namespace ui_theme

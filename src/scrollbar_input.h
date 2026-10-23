#pragma once
#ifndef CATA_SRC_SCROLLBAR_INPUT_H
#define CATA_SRC_SCROLLBAR_INPUT_H

#include <algorithm>
#include <optional>

#include "point.h"

/// Pure geometry and hit testing for the one-column vertical scrollbar drawn by
/// scrollbar::apply() and draw_scrollbar(). Screens keep their own meaning for the
/// returned position (selected row, first visible row, scroll offset).
namespace scrollbar_input
{

/// A drawn scrollbar. offset is window-relative, viewport_size includes both arrows.
struct geometry {
    point offset = point_zero;
    int viewport_size = 0;
    int content_size = 0;
    int viewport_pos = 0;
    bool scroll_to_last = false;
};

/// Row geometry shared with the drawing code.
struct layout {
    int slot_size = 0;
    int bar_size = 0;
    int bar_start = 0;
};

enum class click_part {
    up_arrow,
    down_arrow,
    track,
};

struct click_result {
    click_part part = click_part::track;
    /// Already clamped to the valid viewport range.
    int viewport_pos = 0;
};

/// True when apply() draws arrows and a bar rather than a plain border.
inline auto is_drawn( const geometry &g ) -> bool
{
    return g.content_size > 0 && g.viewport_size >= 2 && g.content_size > g.viewport_size;
}

/// Largest viewport position apply() can represent.
inline auto max_viewport_pos( const geometry &g ) -> int
{
    return g.scroll_to_last ? std::max( 0, g.content_size - 1 )
           : std::max( 0, g.content_size - g.viewport_size );
}

/// Reproduces scrollbar::apply() bar placement.
inline auto layout_for( const geometry &g ) -> layout
{
    auto result = layout{};
    result.slot_size = std::max( 0, g.viewport_size - 2 );
    result.bar_size = std::max( 2, result.slot_size * g.viewport_size / std::max( 1, g.content_size ) );
    const auto scrollable_size = g.scroll_to_last ? g.content_size
                                 : g.content_size - g.viewport_size + 1;
    if( g.viewport_pos <= 0 ) {
        result.bar_start = 0;
    } else if( scrollable_size > 2 ) {
        result.bar_start = ( result.slot_size - 1 - result.bar_size ) * ( g.viewport_pos - 1 ) /
                           ( scrollable_size - 2 ) + 1;
    } else {
        result.bar_start = result.slot_size - result.bar_size;
    }
    return result;
}

/// Hit test a window-relative cell. Returns nullopt off a drawn scrollbar.
inline auto click( const geometry &g, point mouse ) -> std::optional<click_result>
{
    if( !is_drawn( g ) || mouse.x != g.offset.x ) {
        return std::nullopt;
    }
    const auto rel_y = mouse.y - g.offset.y;
    if( rel_y < 0 || rel_y >= g.viewport_size ) {
        return std::nullopt;
    }

    const auto max_pos = max_viewport_pos( g );
    const auto current = std::clamp( g.viewport_pos, 0, max_pos );
    if( rel_y == 0 ) {
        return click_result{ .part = click_part::up_arrow, .viewport_pos = std::max( 0, current - 1 ) };
    }
    if( rel_y == g.viewport_size - 1 ) {
        return click_result{ .part = click_part::down_arrow, .viewport_pos = std::min( max_pos, current + 1 ) };
    }

    const auto lay = layout_for( g );
    if( lay.slot_size <= 0 ) {
        return std::nullopt;
    }
    const auto max_bar_start = std::max( 0, lay.slot_size - lay.bar_size );
    const auto target_bar_start = std::clamp( rel_y - 1 - lay.bar_size / 2, 0, max_bar_start );
    auto target = 0;
    if( target_bar_start > 0 ) {
        const auto span = lay.slot_size - 1 - lay.bar_size;
        if( span <= 0 || max_pos <= 1 ) {
            target = max_pos;
        } else {
            const auto numerator = static_cast<long long>( target_bar_start - 1 ) * ( max_pos - 1 );
            target = 1 + static_cast<int>( numerator / span );
        }
    }
    return click_result{ .part = click_part::track, .viewport_pos = std::clamp( target, 0, max_pos ) };
}

} // namespace scrollbar_input

#endif // CATA_SRC_SCROLLBAR_INPUT_H

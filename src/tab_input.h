#pragma once
#ifndef CATA_SRC_TAB_INPUT_H
#define CATA_SRC_TAB_INPUT_H

#include <cstddef>
#include <optional>
#include <string>
#include <vector>

#include "catacharset.h"
#include "output.h"

/// Hit testing for the horizontal tab strip drawn by draw_tabs(). A tab box
/// spans rows 0-2 of the strip window, so only the horizontal position matters.
namespace tab_input
{

/// A strip to hit-test; texts, current and max_width must match the
/// draw_tabs( w, texts, current, max_width ) call that drew the strip.
struct query {
    const std::vector<std::string> &texts;
    size_t current = 0;
    int max_width = 0;
    int x = 0;
};

/// Index of the drawn tab whose box contains the queried column, or nullopt
/// between tabs.
inline auto index_at( const query &q ) -> std::optional<int>
{
    constexpr auto tab_step = 3;
    const auto count = static_cast<int>( q.texts.size() );
    auto total_used_width = 0;
    auto current_end = 0;
    for( auto i = 0; i < count; ++i ) {
        total_used_width += utf8_width( q.texts[i] ) + tab_step;
        if( i == static_cast<int>( q.current ) ) {
            current_end = total_used_width;
        }
    }
    auto start = 0;
    calcStartPos( start, current_end, q.max_width, total_used_width );
    auto start_i = 0;
    if( start != 0 ) {
        auto acc = 0;
        for( auto i = 0; i < count; ++i ) {
            acc += utf8_width( q.texts[i] ) + tab_step;
            if( acc >= start ) {
                start_i = i + 1;
                break;
            }
        }
    }
    auto tab_x = 2;
    for( auto i = start_i; i < count; ++i ) {
        const auto tab_width = utf8_width( q.texts[i] );
        const auto newx = tab_x + tab_width + tab_step;
        if( newx > q.max_width ) {
            break;
        }
        // The box plus the selected tab's '<' and '>' markers.
        if( q.x >= tab_x - 1 && q.x <= tab_x + tab_width + 1 ) {
            return i;
        }
        tab_x = newx;
    }
    return std::nullopt;
}

} // namespace tab_input

#endif // CATA_SRC_TAB_INPUT_H

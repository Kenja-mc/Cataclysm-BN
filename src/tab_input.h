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

/// Index of the drawn tab whose box contains column x, or nullopt between tabs.
/// texts, current and max_width must match the draw_tabs( w, texts, current,
/// max_width ) call that drew the strip.
inline auto index_at( const std::vector<std::string> &texts, size_t current,
                      int max_width, int x ) -> std::optional<int>
{
    constexpr int tab_step = 3;
    int total_used_width = 0;
    int current_end = 0;
    for( size_t i = 0; i < texts.size(); ++i ) {
        total_used_width += utf8_width( texts[i] ) + tab_step;
        if( i == current ) {
            current_end = total_used_width;
        }
    }
    int start = 0;
    calcStartPos( start, current_end, max_width, total_used_width );
    size_t start_i = 0;
    if( start != 0 ) {
        int acc = 0;
        for( size_t i = 0; i < texts.size(); ++i ) {
            acc += utf8_width( texts[i] ) + tab_step;
            if( acc >= start ) {
                start_i = i + 1;
                break;
            }
        }
    }
    int tab_x = 2;
    for( size_t i = start_i; i < texts.size(); ++i ) {
        const int tab_width = utf8_width( texts[i] );
        const int newx = tab_x + tab_width + tab_step;
        if( newx > max_width ) {
            break;
        }
        // The box plus the selected tab's '<' and '>' markers.
        if( x >= tab_x - 1 && x <= tab_x + tab_width + 1 ) {
            return static_cast<int>( i );
        }
        tab_x = newx;
    }
    return std::nullopt;
}

} // namespace tab_input

#endif // CATA_SRC_TAB_INPUT_H

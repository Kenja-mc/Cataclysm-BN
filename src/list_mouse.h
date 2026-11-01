#pragma once
#ifndef CATA_SRC_LIST_MOUSE_H
#define CATA_SRC_LIST_MOUSE_H

#include <chrono>
#include <cstdint>

/// Shared behaviour for confirming a list row with the mouse in the Modern scheme.
namespace list_mouse
{

/// True when Modern's list mouse option is on. Classic keeps upstream mouse handling.
auto enabled() -> bool;

/// Pairs a second click on the same row with the first one. The pair must fall
/// within one double-click window; a later click starts a new pair.
class click_state
{
    public:
        auto second( int row ) -> bool;
        auto second( const void *row ) -> bool;
        void reset();

    private:
        auto second_token( std::uintptr_t token ) -> bool;

        std::uintptr_t token = 0;
        std::chrono::steady_clock::time_point when{};
        bool armed = false;
};

} // namespace list_mouse

#endif // CATA_SRC_LIST_MOUSE_H

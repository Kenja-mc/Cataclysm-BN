#pragma once
#ifndef CATA_SRC_LIST_MOUSE_H
#define CATA_SRC_LIST_MOUSE_H

#include <chrono>
#include <cstdint>

namespace list_mouse
{

auto enabled() -> bool;

class click_state
{
    public:
        auto second( int row ) -> bool;
        auto second( const void *row ) -> bool;
        auto reset() -> void;

    private:
        auto second_token( std::uintptr_t token ) -> bool;

        std::uintptr_t token = 0;
        std::chrono::steady_clock::time_point when{};
        bool armed = false;
};

}

#endif

#include "list_mouse.h"

#include "options.h"

namespace list_mouse
{

namespace
{
constexpr auto double_click_window = std::chrono::milliseconds( 500 );
} // namespace

auto enabled() -> bool
{
    return get_option<std::string>( "CONTROL_SCHEME" ) == "modern" &&
           get_option<bool>( "MODERN_LIST_MOUSE" );
}

auto click_state::second_token( std::uintptr_t new_token ) -> bool
{
    const auto now = std::chrono::steady_clock::now();
    if( armed && token == new_token && now - when <= double_click_window ) {
        armed = false;
        return true;
    }
    token = new_token;
    when = now;
    armed = true;
    return false;
}

auto click_state::second( int row ) -> bool
{
    return second_token( static_cast<std::uintptr_t>( row ) + 1 );
}

auto click_state::second( const void *row ) -> bool
{
    return second_token( reinterpret_cast<std::uintptr_t>( row ) );
}

void click_state::reset()
{
    armed = false;
}

} // namespace list_mouse

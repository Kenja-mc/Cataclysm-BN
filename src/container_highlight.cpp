#include "container_highlight.h"

#include "avatar.h"
#include "map/map.h"
#include "options.h"

namespace
{

auto is_container( const map &here, const tripoint_bub_ms &p ) -> bool
{
    return here.has_flag( "CONTAINER", p );
}

auto record_contents( avatar &you, const map &here, const tripoint_bub_ms &p ) -> void
{
    if( !is_container( here, p ) || !here.could_see_items( p, you ) ||
        !you.sees( p ) ) {
        return;
    }
    const auto abs = bub_to_abs( p );
    if( here.sees_some_items( p, you ) ) {
        if( !you.has_seen_container_contents( abs ) ) {
            you.remember_container_contents( abs );
        }
    } else if( you.has_seen_container_contents( abs ) ) {
        you.forget_container_contents( abs );
    }
}

}

namespace container_highlight
{

auto level( const avatar &you, const map &here, const tripoint_bub_ms &p ) -> int
{
    if( !get_option<bool>( "CONTAINER_HIGHLIGHT" ) || !is_container( here, p ) ||
        !you.sees( p ) ) {
        return 0;
    }
    if( here.could_see_items( p, you ) ) {
        return here.sees_some_items( p, you ) ? 1 : 0;
    }
    return you.has_seen_container_contents( bub_to_abs( p ) ) ? 2 : 0;
}

auto observe( avatar &you, const map &here ) -> void
{
    for( const tripoint_bub_ms &p : here.points_in_radius( you.bub_pos(), 1 ) ) {
        record_contents( you, here, p );
    }
}

auto tint( const int level ) -> nc_color
{
    return level == 1 ? c_yellow : c_light_cyan;
}

}

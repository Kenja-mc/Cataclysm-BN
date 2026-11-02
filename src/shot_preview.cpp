#include "shot_preview.h"

#include <utility>

namespace
{

shot_preview::state preview_state;

} // namespace

namespace shot_preview
{

auto set( state next ) -> void
{
    preview_state = std::move( next );
}

auto clear() -> void
{
    preview_state = state{};
}

auto active() -> bool
{
    return preview_state.active;
}

auto current() -> const state & // *NOPAD*
{
    return preview_state;
}

auto label_at( const tripoint_bub_ms &p ) -> std::string
{
    if( !preview_state.active || !preview_state.aim_label ||
        preview_state.aim_label->pos != p ) {
        return std::string();
    }
    return preview_state.aim_label->label;
}

} // namespace shot_preview

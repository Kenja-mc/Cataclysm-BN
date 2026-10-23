#pragma once

#include <string>

#include "action.h"

/// How the player reaches an action: its key when bound, otherwise the way the active control
/// scheme offers it ("i → item → Wield", "Space", "Return → Info → ..."). Modern unbinds many
/// classic map keys, and text that names a key must still tell the player what to do.
auto action_route( action_id act ) -> std::string;

/// The key or route for a keybinding id; ids without an `action_id` (e.g. NEXT_TARGET) use
/// their map binding.
auto action_route( const std::string &id ) -> std::string;

/// The key for an id in an explicit input context, e.g. the aiming screen's FIRE or QUIT.
/// An id with no binding in that context falls back to the default-mode route.
auto action_route( const std::string &id, const std::string &context ) -> std::string;

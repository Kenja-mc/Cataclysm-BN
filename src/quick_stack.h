#pragma once

class avatar;

/// Terraria-style storage helpers that replace hand-built sorting zones.
namespace quick_stack
{

/// Moves carried, non-favorite items into nearby storage (furniture or vehicle cargo) that already
/// holds the same item or is dominated by the same item category.
auto stash_inventory( avatar &you ) -> void;

/// Distributes the pile under the player into matching storage, or onto loose piles of the exact same item.
auto sort_pile( avatar &you ) -> void;

} // namespace quick_stack

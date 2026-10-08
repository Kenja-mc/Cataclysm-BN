#pragma once

class avatar;

/// Terraria-style storage helpers that replace hand-built sorting zones.
namespace quick_stack
{

/// Moves carried, non-favorite items onto nearby piles or storage that already hold the same item,
/// or into nearby storage dominated by the same item category.
auto stash_inventory( avatar &you ) -> void;

/// Distributes the pile under the player across nearby piles and storage using the same rules.
auto sort_pile( avatar &you ) -> void;

} // namespace quick_stack

#pragma once

#include <vector>

class avatar;
class item;

/// Pours the charges of partly used copies of a tool into one, like combining drainables in Project
/// Zomboid. Charges are conserved; emptied copies are destroyed.
namespace combine_items
{

/// A tool holding its own charges, partly used, that nothing else refills.
auto is_eligible( const item &it ) -> bool;
/// The other carried copies `target` can take charges from.
auto partners( const avatar &you, const item &target ) -> std::vector<item *>;
/// Fills `target` from its partners, emptiest first.
auto combine( avatar &you, item &target ) -> void;

} // namespace combine_items

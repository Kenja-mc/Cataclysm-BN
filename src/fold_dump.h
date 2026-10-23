#pragma once

#include <string>
#include <vector>

/// QA-only dump used by tools/fold_equivalence. Spawns items through the normal loaders and
/// writes their properties as JSON so a folded item can be compared with its mainline original.
auto dump_folded_items( const std::vector<std::string> &opts ) -> bool;

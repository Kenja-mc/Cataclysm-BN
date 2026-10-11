#pragma once

#include <vector>

#include "memory_fast.h"

class avatar;
class monster;

namespace smart_safemode
{

/// Whether safe mode should care about `mon`: always when the SMART_SAFEMODE option is off,
/// otherwise only when `can_reach_soon` says so.
auto threatens( const monster &mon, avatar &you ) -> bool;

/// Whether `mon` can hurt you soon: it is next to you, has an attack that reaches without a
/// walking route, or can walk to you within twice the safe-mode distance. Fleeing monsters
/// cannot. Answers are kept for the rest of the turn.
auto can_reach_soon( const monster &mon, avatar &you ) -> bool;

/// Check a group with bounded route work. Unexamined monsters conservatively stop travel.
auto any_threatens( const std::vector<const monster *> &mons, avatar &you ) -> bool;
auto any_threatens( const std::vector<shared_ptr_fast<monster>> &mons, avatar &you ) -> bool;

/// Discard route answers when terrain, furniture, fields or vehicles change passability.
auto invalidate_reach_cache() -> void;

} // namespace smart_safemode

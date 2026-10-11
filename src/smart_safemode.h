#pragma once

class avatar;
class monster;

namespace smart_safemode
{

/// Whether safe mode should care about `mon`: always when the SMART_SAFEMODE option is off,
/// otherwise only when `can_reach_soon` says so.
auto threatens( const monster &mon, avatar &you ) -> bool;

/// Whether `mon` can hurt you soon: it is next to you, has an attack that reaches without a
/// walking route, or can walk to you within twice the safe-mode distance. Fleeing monsters
/// cannot.
auto can_reach_soon( const monster &mon, avatar &you ) -> bool;

} // namespace smart_safemode

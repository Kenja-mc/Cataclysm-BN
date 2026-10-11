#pragma once

class avatar;
class monster;

namespace smart_safemode
{

auto threatens( const monster &mon, avatar &you ) -> bool;

/// Whether the monster can walk a route to the player soon, ignoring the
/// SMART_SAFEMODE option that decides whether safe mode should care.
auto reaches_soon( const monster &mon, avatar &you ) -> bool;

} // namespace smart_safemode

#pragma once

#include <vector>

#include "memory_fast.h"

class avatar;
class monster;

namespace smart_safemode
{

auto threatens( const monster &mon, avatar &you ) -> bool;

auto can_reach_soon( const monster &mon, avatar &you ) -> bool;

auto any_threatens( const std::vector<const monster *> &mons, avatar &you ) -> bool;
auto any_threatens( const std::vector<shared_ptr_fast<monster>> &mons, avatar &you ) -> bool;

auto invalidate_reach_cache() -> void;

}

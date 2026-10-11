#pragma once

class avatar;
class monster;

namespace smart_safemode
{

auto threatens( const monster &mon, avatar &you ) -> bool;

} // namespace smart_safemode

#pragma once

#include <vector>

class avatar;
class item;

namespace combine_items
{

auto is_eligible( const item &it ) -> bool;
auto partners( const avatar &you, const item &target ) -> std::vector<item *>;
auto combine( avatar &you, item &target ) -> void;

}

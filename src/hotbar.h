#pragma once

#include <string>

#include "color.h"

class avatar;
class item;

/// Six quick slots that each remember an item type and run the same action the Use menu would
/// run on the first matching carried item. Slots are saved with the character.
namespace hotbar
{

constexpr auto slots = 6;

struct slot_view {
    bool assigned = false;
    /// Map symbol and colour of the item type.
    std::string symbol;
    nc_color color = c_light_gray;
    std::string name;
    /// How many matching items (or charges) are carried; zero greys the slot.
    int count = 0;
    bool wielded = false;
};

auto view( const avatar &you, int slot ) -> slot_view;

/// Runs the slot's item: read, eat, wield, wear or activate it, as Use does.
auto use( avatar &you, int slot ) -> void;
/// Asks for a slot and then an item (or none, to clear it).
auto assign( avatar &you ) -> void;
/// What the Use menu does with a chosen item.
auto use_item( avatar &you, item *loc ) -> void;

} // namespace hotbar

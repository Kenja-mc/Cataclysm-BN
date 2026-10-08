#pragma once

#include <optional>
#include <string>
#include <vector>

#include "string_id.h"
#include "translations.h"

class item;
class JsonObject;
struct stack_modifier;

using stack_modifier_id = string_id<stack_modifier>;

/// A trait carried by some units of a count-by-charges stack, such as black-powder handloads mixed
/// into factory rounds. The stack keeps one item type and counts how many of its units carry the
/// trait, so variants stack together instead of each needing its own item type.
struct stack_modifier {
    stack_modifier_id id;
    bool was_loaded = false;

    translation name;
    /// Multipliers applied to a shot fired with a modified round.
    float damage = 1.0f;
    float armor_penetration = 1.0f;
    float dispersion = 1.0f;
    float recoil = 1.0f;
    /// Modified units cannot be disassembled (their components differ from the base recipe).
    bool blocks_disassembly = false;

    void load( const JsonObject &jo, const std::string &src );
    void check() const {}
};

struct stack_modifier_count {
    stack_modifier_id id;
    int count = 0;
};

namespace stack_modifiers
{

void load( const JsonObject &jo, const std::string &src );
void reset();
void check_consistency();

auto count( const item &it, const stack_modifier_id &mod ) -> int;
auto set_count( item &it, const stack_modifier_id &mod, int n ) -> void;
/// Every modifier with a non-zero count on `it`.
auto on( const item &it ) -> std::vector<stack_modifier_count>;
/// True for the item variables that hold modifier counts; stacking ignores them.
auto is_count_var( const std::string &key ) -> bool;

/// Adds the modified units of `from` to `into`; call before the charges are summed.
auto merge( item &into, const item &from ) -> void;
/// Moves the share of modified units that leaves with `qty` of `from`'s charges onto `to`, adding
/// to whatever `to` already counts. Call before `from` loses the charges.
auto transfer( item &from, item &to, int qty ) -> void;
/// Same as transfer, but `part` is a fresh copy of `from` whose counts are replaced.
auto split( item &from, item &part, int qty ) -> void;
/// Keeps counts within `total` units after charges were removed without choosing which ones.
auto clamp( item &it, int total ) -> void;
/// Picks the unit about to be used from `source` (holding `total` units) and removes it from the counts.
auto take_one( item &source, int total ) -> std::optional<stack_modifier_id>;
/// ", 10 black powder" style suffix for item names; empty when no unit is modified.
auto describe( const item &it ) -> std::string;

} // namespace stack_modifiers

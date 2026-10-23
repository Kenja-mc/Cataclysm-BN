#pragma once

#include <optional>
#include <set>
#include <string>
#include <vector>

#include "string_id.h"
#include "translations.h"
#include "type_id.h"

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
    /// Per-unit multipliers for retail and post-apocalypse value.
    float price = 1.0f;
    float price_postapoc = 1.0f;
    std::set<ammo_effect_str_id> ammo_effects;
    std::set<ammo_effect_str_id> remove_ammo_effects;

    void load( const JsonObject &jo, const std::string &src );
    void check() const {}
    auto apply_ammo_effects( std::set<ammo_effect_str_id> &effects ) const -> void;
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
/// Removes a proportional share of modifier counts before `it` loses `qty` charges.
auto consume( item &it, int qty ) -> void;
/// Selects a unit without consuming it, so failed firing attempts leave counts unchanged.
auto select_one( const item &source, int total ) -> std::optional<stack_modifier_id>;
/// Consumes the selected unit and a proportional share of any additional charges.
auto consume_selected( item &source, int qty,
                       const std::optional<stack_modifier_id> &selected ) -> void;
/// Weighted value of modified and plain units; `total` is the number of charges being priced.
auto price_multiplier( const item &it, int total, bool practical ) -> float;
/// Number of units with an effect, using one unit for empty-item metadata.
auto ammo_effect_count( const item &source, const ammo_effect_str_id &effect,
                        bool base_has_effect ) -> int;
/// ", 10 black powder" style suffix for item names; empty when no unit is modified.
auto describe( const item &it ) -> std::string;

} // namespace stack_modifiers

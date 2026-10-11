#pragma once
#include <cstdint>

#include <map>
#include <utility>
#include <vector>

#include "type_id.h"

class inventory;
struct item_comp;
class recipe;
class recipe_subset;

namespace craft_chain
{

/// Menu-level producer cache.  Everything stored in it is independent of the
/// goal recipe, so one instance is shared across all goals the player browses.
/// Clear it when the crafting inventory, the known recipes or the crafter
/// change; a stale cache would claim the wrong parts are craftable.
struct production_info {
    /// Non-nested, known recipes that produce a component type, as their result
    /// or as a byproduct, in preference order (result makers first).  Filled
    /// once per component type because the search is goal independent.
    std::map<itype_id, std::vector<const recipe *>> producers;
    /// Whether a producer can be crafted right now, per producer recipe.
    std::map<const recipe *, bool> craftable;
    /// Real units of a component type that one batch of a producer yields.
    std::map<std::pair<const recipe *, itype_id>, std::int64_t> units;

    auto clear() -> void
    {
        producers.clear();
        craftable.clear();
        units.clear();
    }
};

/// The producers a part lookup found for one component.
struct part_producers {
    /// A producer that can be crafted right now, or nullptr.
    const recipe *craftable = nullptr;
    /// A known producer that cannot be crafted right now, or nullptr.
    const recipe *known = nullptr;
};

/// What a part lookup needs: the recipe the player wants, what they have and know.
struct part_query {
    const recipe &goal;
    const inventory &crafting_inv;
    const recipe_subset &known_recipes;
    int goal_batch = 1;
    /// When non-null, producers, craftability and unit counts are cached here
    /// and shared across goals, so no lookup repeats work it already did.
    production_info *cache = nullptr;
};

/// The recipe to craft right now that supplies a missing component of the goal, or
/// nullptr when there is none. Depth 1 only.
auto find_part_recipe( const part_query &query ) -> const recipe *;

/// Like find_part_recipe but checks a single component directly; uses the cache
/// when the query carries one.
auto find_part_recipe( const part_query &query, const item_comp &comp ) -> const recipe *;

/// Whether `comp` of the goal can be crafted right now; drives the "(can make)" tag.
auto can_craft_part( const part_query &query, const item_comp &comp ) -> bool;

/// Whether `comp` has a known producer that cannot be crafted right now; drives
/// the "[parts:known]" marker and the panel's unavailable-producer section.
auto has_known_unavailable_producer( const part_query &query, const item_comp &comp ) -> bool;

/// Returns a known producer that cannot be crafted right now (or nullptr).
auto find_known_producer( const part_query &query, const item_comp &comp ) -> const recipe *;

/// How many units of `type` one batch of `producer` really yields, counting
/// actual result charges, container contents and byproducts.  The real items
/// are only built once per producer and component when the query has a cache.
auto units_per_batch( const part_query &query, const recipe &producer,
                      const itype_id &type ) -> std::int64_t;

} // namespace craft_chain

#pragma once

#include <map>
#include <set>

class inventory;
struct item_comp;
class recipe;
class recipe_subset;

namespace craft_chain
{

/// Cached producer-lookup state for a single goal recipe.  Distinguishes
/// producers that exist but cannot be crafted now from those that can.
struct production_info {
    /// Known non-nested recipes (excluding the goal) that produce a component
    /// type and can be crafted right now.
    std::map<itype_id, const recipe *> craftable_producers;
    /// Known non-nested recipes (excluding the goal) that produce a component
    /// type but cannot be crafted right now (missing tools/materials).
    std::map<itype_id, const recipe *> known_producers;
    /// Component types for which a producer was searched but none was found.
    std::set<itype_id> no_producer;
};

/// What a part lookup needs: the recipe the player wants, what they have and know.
struct part_query {
    const recipe &goal;
    const inventory &crafting_inv;
    const recipe_subset &known_recipes;
    int goal_batch = 1;
    /// When non-null, producers are looked up once per goal and cached here.
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

} // namespace craft_chain

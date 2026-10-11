#pragma once

class inventory;
struct item_comp;
class recipe;
class recipe_subset;

namespace craft_chain
{

/// What a part lookup needs: the recipe the player wants, what they have and know.
struct part_query {
    const recipe &goal;
    const inventory &crafting_inv;
    const recipe_subset &known_recipes;
    int goal_batch = 1;
};

/// The recipe to craft right now that supplies a missing component of the goal, or
/// nullptr when there is none. Depth 1 only.
auto find_part_recipe( const part_query &query ) -> const recipe *;

/// Whether `comp` of the goal can be crafted right now; drives the "(can make)" tag.
auto can_craft_part( const part_query &query, const item_comp &comp ) -> bool;

} // namespace craft_chain

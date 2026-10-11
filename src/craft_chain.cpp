#include "craft_chain.h"

#include <algorithm>
#include <vector>

#include "inventory.h"
#include "recipe.h"
#include "recipe_dictionary.h"
#include "requirements.h"

namespace
{

/// Tools and qualities count too, so this never promises a recipe that would stall.
auto craftable_now( const inventory &crafting_inv, const recipe &producer ) -> bool
{
    return producer.simple_requirements().can_make_with_inventory(
               crafting_inv, producer.get_component_filter( recipe_filter_flags::none ),
               1, cost_adjustment::start_only );
}

/// The first known recipe other than the goal that makes `comp` and can be crafted now.
/// Recipes whose main result is the part come before byproduct recipes.
auto producer_for( const craft_chain::part_query &query, const item_comp &comp ) -> const recipe *
{
    auto producers = query.known_recipes.search_result( comp.type );
    std::erase_if( producers, [&]( const recipe * r ) {
        return r == nullptr || r->is_nested() || r->ident() == query.goal.ident();
    } );
    std::ranges::stable_sort( producers, std::ranges::greater(), [&]( const recipe * r ) {
        return r->result() == comp.type;
    } );
    const auto found = std::ranges::find_if( producers, [&]( const recipe * r ) {
        return craftable_now( query.crafting_inv, *r );
    } );
    return found == producers.end() ? nullptr : *found;
}

} // namespace

namespace craft_chain
{

auto find_part_recipe( const part_query &query ) -> const recipe *
{
    const auto &filter = query.goal.get_component_filter( recipe_filter_flags::none );
    // Tools and qualities cannot be crafted, so only components are considered.
    for( const auto &group : query.goal.simple_requirements().get_components() ) {
        // A group with an available alternative does not block the recipe.
        const auto blocked = std::ranges::none_of( group, [&]( const item_comp & comp ) {
            return comp.has( query.crafting_inv, filter, query.goal_batch );
        } );
        if( !blocked ) {
            continue;
        }
        for( const auto &comp : group ) {
            if( const auto *producer = producer_for( query, comp ) ) {
                return producer;
            }
        }
    }
    return nullptr;
}

auto can_craft_part( const part_query &query, const item_comp &comp ) -> bool
{
    return producer_for( query, comp ) != nullptr;
}

} // namespace craft_chain

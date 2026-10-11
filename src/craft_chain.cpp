#include "craft_chain.h"

#include <algorithm>
#include <map>
#include <set>
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

/// Search the known recipes for one that makes `comp`.  Results are memoized
/// into `cache` when the query carries one; cache lookups never trigger a new
/// recipe search.
///
/// Returns a pair of (craftable_producer, known_producer) — one may be null.
/// craftable_producer: can be crafted right now.
/// known_producer: exists but cannot be crafted right now (missing tools/materials).
auto producers_for( const craft_chain::part_query &query, const item_comp &comp,
                    craft_chain::production_info *cache )
-> std::pair<const recipe *, const recipe *>
{
    if( cache != nullptr ) {
        if( auto it = cache->craftable_producers.find( comp.type );
            it != cache->craftable_producers.end() ) {
            return { it->second, nullptr };
        }
        if( auto it = cache->known_producers.find( comp.type );
            it != cache->known_producers.end() ) {
            return { nullptr, it->second };
        }
        if( cache->no_producer.contains( comp.type ) ) {
            return { nullptr, nullptr };
        }
    }

    auto all_producers = query.known_recipes.search_result( comp.type );
    std::erase_if( all_producers, [&]( const recipe * r ) {
        return r == nullptr || r->is_nested() || r->ident() == query.goal.ident();
    } );
    std::ranges::stable_sort( all_producers, std::ranges::greater(), [&]( const recipe * r ) {
        return r->result() == comp.type;
    } );

    const recipe *craftable = nullptr;
    const recipe *known = nullptr;
    for( const recipe *r : all_producers ) {
        if( known == nullptr ) {
            known = r;
        }
        if( craftable_now( query.crafting_inv, *r ) ) {
            craftable = r;
            break;
        }
    }

    if( cache != nullptr ) {
        if( craftable != nullptr ) {
            cache->craftable_producers.emplace( comp.type, craftable );
        } else if( known != nullptr ) {
            cache->known_producers.emplace( comp.type, known );
        } else {
            cache->no_producer.insert( comp.type );
        }
    }
    return { craftable, known };
}

} // namespace

namespace craft_chain
{

auto find_part_recipe( const part_query &query, const item_comp &comp ) -> const recipe *
{
    return producers_for( query, comp, query.cache ).first;
}

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
            if( const auto *producer = producers_for( query, comp, query.cache ).first ) {
                return producer;
            }
        }
    }
    return nullptr;
}

auto can_craft_part( const part_query &query, const item_comp &comp ) -> bool
{
    return producers_for( query, comp, query.cache ).first != nullptr;
}

auto has_known_unavailable_producer( const part_query &query, const item_comp &comp ) -> bool
{
    return producers_for( query, comp, query.cache ).second != nullptr;
}

auto find_known_producer( const part_query &query, const item_comp &comp ) -> const recipe *
{
    return producers_for( query, comp, query.cache ).second;
}
} // namespace craft_chain

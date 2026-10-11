#include "craft_chain.h"

#include <algorithm>
#include <map>
#include <utility>
#include <vector>

#include "inventory.h"
#include "item.h"
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

/// Resolve the producers of `type` for one goal.  The candidate list itself is
/// goal independent, so it is cached per component and shared across goals; the
/// goal recipe is skipped per query, which keeps the shared cache correct.
auto producers_for( const craft_chain::part_query &query, const itype_id &type )
-> craft_chain::part_producers
{
    const std::vector<const recipe *> *candidates = nullptr;
    std::vector<const recipe *> searched;
    if( query.cache != nullptr ) {
        if( auto it = query.cache->producers.find( type ); it != query.cache->producers.end() ) {
            candidates = &it->second;
        }
    }
    if( candidates == nullptr ) {
        searched = query.known_recipes.search_result( type );
        // Nested category stubs and obsolete recipes never produce a part.
        std::erase_if( searched, [&]( const recipe * r ) {
            return r == nullptr || r->obsolete || r->is_nested();
        } );
        // Recipes whose result is the component itself are preferred over ones
        // that only make it as a byproduct.
        std::ranges::stable_sort( searched, std::ranges::greater(), [&]( const recipe * r ) {
            return r->result() == type;
        } );
        if( query.cache != nullptr ) {
            candidates = &query.cache->producers.emplace( type, searched ).first->second;
        } else {
            candidates = &searched;
        }
    }

    auto out = craft_chain::part_producers{};
    for( const recipe *r : *candidates ) {
        // The goal recipe is never a producer of its own missing part.
        if( r == &query.goal || r->ident() == query.goal.ident() ) {
            continue;
        }
        if( out.known == nullptr ) {
            out.known = r;
        }
        bool craftable = false;
        if( query.cache == nullptr ) {
            craftable = craftable_now( query.crafting_inv, *r );
        } else if( auto it = query.cache->craftable.find( r ); it != query.cache->craftable.end() ) {
            craftable = it->second;
        } else {
            craftable = craftable_now( query.crafting_inv, *r );
            query.cache->craftable.emplace( r, craftable );
        }
        if( craftable ) {
            out.craftable = r;
            break;
        }
    }
    return out;
}

/// How many units of `type` these crafted items carry, looking inside a
/// produced container so contained results count towards the component too.
auto units_of_type( const std::vector<detached_ptr<item>> &items, const itype_id &type ) -> int
{
    int units = 0;
    for( const auto &it : items ) {
        if( it->typeId() == type ) {
            units += it->count_by_charges() ? it->charges : 1;
        } else if( it->is_container() ) {
            for( const item *contained : it->contents.all_items_top() ) {
                if( contained->typeId() == type ) {
                    units += contained->count_by_charges() ? contained->charges : 1;
                }
            }
        }
    }
    return units;
}

} // namespace

namespace craft_chain
{

auto find_part_recipe( const part_query &query, const item_comp &comp ) -> const recipe *
{
    return producers_for( query, comp.type ).craftable;
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
            if( const auto *producer = find_part_recipe( query, comp ) ) {
                return producer;
            }
        }
    }
    return nullptr;
}

auto can_craft_part( const part_query &query, const item_comp &comp ) -> bool
{
    return find_part_recipe( query, comp ) != nullptr;
}

auto has_known_unavailable_producer( const part_query &query, const item_comp &comp ) -> bool
{
    return producers_for( query, comp.type ).known != nullptr;
}

auto find_known_producer( const part_query &query, const item_comp &comp ) -> const recipe *
{
    return producers_for( query, comp.type ).known;
}

auto units_per_batch( const part_query &query, const recipe &producer,
                      const itype_id &type ) -> int
{
    const auto key = std::make_pair( &producer, type );
    if( query.cache != nullptr ) {
        if( auto it = query.cache->units.find( key ); it != query.cache->units.end() ) {
            return it->second;
        }
    }
    // One batch, built the way crafting itself builds it.
    const int units = units_of_type( producer.create_results( 1 ), type ) +
                      units_of_type( producer.create_byproducts( 1 ), type );
    if( query.cache != nullptr ) {
        query.cache->units.emplace( key, units );
    }
    return units;
}

} // namespace craft_chain

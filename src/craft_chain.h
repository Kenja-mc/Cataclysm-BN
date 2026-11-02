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

struct production_info {
    std::map<itype_id, std::vector<const recipe *>> producers;
    std::map<const recipe *, bool> craftable;
    std::map<const recipe *, std::map<itype_id, std::int64_t>> units;

    auto clear() -> void {
        producers.clear();
        craftable.clear();
        units.clear();
    }
};

struct part_producers {
    const recipe *craftable = nullptr;
    const recipe *known = nullptr;
};

struct part_query {
    const recipe &goal;
    const inventory &crafting_inv;
    const recipe_subset &known_recipes;
    int goal_batch = 1;
    production_info *cache = nullptr;
};

auto find_part_recipe( const part_query &query ) -> const recipe *; // *NOPAD*

auto find_part_recipe( const part_query &query,
                       const item_comp &comp ) -> const recipe *; // *NOPAD*

auto can_craft_part( const part_query &query, const item_comp &comp ) -> bool;

auto has_known_unavailable_producer( const part_query &query, const item_comp &comp ) -> bool;

auto find_known_producer( const part_query &query,
                          const item_comp &comp ) -> const recipe *; // *NOPAD*

auto units_per_batch( const part_query &query, const recipe &producer,
                      const itype_id &type ) -> std::int64_t;

}

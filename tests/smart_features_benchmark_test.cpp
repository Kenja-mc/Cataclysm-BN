#include "avatar.h"
#include "calendar.h"
#include "cata_utility.h"
#include "catch/catch.hpp"
#include "enemy_indicators.h"
#include "game.h"
#include "map/map.h"
#include "map_helpers.h"
#include "monster.h"
#include "options_helpers.h"
#include "player_helpers.h"
#include "smart_safemode.h"
#include "state_helpers.h"
#include "type_id.h"

#include <algorithm>
#include <ranges>
#include <vector>

namespace {

/// A horde on every side of the player, from just outside melee range to the edge of sight.
auto spawn_horde(const tripoint_bub_ms& center, const int count) -> std::vector<monster*> {
    auto horde = std::vector<monster*>();
    for (auto ring = 6; static_cast<int>(horde.size()) < count; ring += 3) {
        for (auto dx = -ring; dx <= ring && static_cast<int>(horde.size()) < count; dx += 4) {
            for (const auto dy : {-ring, ring}) {
                if (static_cast<int>(horde.size()) < count) {
                    horde.push_back(
                        &spawn_test_monster("mon_zombie", center + tripoint_rel_ms(dx, dy, 0)));
                }
            }
        }
    }
    return horde;
}

/// A wall two tiles out that no zombie can break, so every route search fails after exploring
/// all it may.
auto wall_in(const tripoint_bub_ms& center, const ter_id& wall) -> void {
    auto& here = get_map();
    for (auto dx = -2; dx <= 2; dx++) {
        for (auto dy = -2; dy <= 2; dy++) {
            if (std::max(std::abs(dx), std::abs(dy)) == 2) {
                here.ter_set(center + tripoint_rel_ms(dx, dy, 0), wall);
            }
        }
    }
}

/// Each call is a new turn, so the per-turn answer cache does not hide the route searches.
auto reachable_count(const std::vector<monster*>& horde, avatar& you) -> int {
    calendar::turn += 1_turns;
    return static_cast<int>(std::ranges::count_if(horde, [&](const monster* mon) {
        return smart_safemode::can_reach_soon(*mon, you);
    }));
}

auto prepare_daylight_field() -> tripoint_bub_ms {
    clear_all_state();
    clear_map();
    set_time(calendar::turn_zero + 12_hours);
    auto& you = get_avatar();
    const auto center = you.bub_pos();
    get_map().build_map_cache(center.z());
    return center;
}

} // namespace

TEST_CASE("smart safe mode reach test with a horde", "[.][benchmark][smart_safemode]") {
    const auto restore_turn = restore_on_out_of_scope<time_point>(calendar::turn);
    const auto cleanup = on_out_of_scope([] { clear_all_state(); });
    const auto center = prepare_daylight_field();
    auto& you = get_avatar();
    const auto horde = spawn_horde(center, 100);
    const override_option smart("SMART_SAFEMODE", "true");

    SECTION("open ground") {
        BENCHMARK("can_reach_soon for 100 zombies, open ground") {
            return reachable_count(horde, you);
        };
    }
    SECTION("walled in") {
        wall_in(center, ter_id("t_concrete_wall"));
        get_map().build_map_cache(center.z());
        BENCHMARK("can_reach_soon for 100 zombies, player walled in") {
            return reachable_count(horde, you);
        };
        const auto seen = std::vector<const monster*>(horde.begin(), horde.end());
        auto bounded =
            horde | std::views::take(13) | std::ranges::to<std::vector<const monster*>>();
        CHECK(smart_safemode::any_threatens(bounded, you));
        bounded.pop_back();
        CHECK_FALSE(smart_safemode::any_threatens(bounded, you));
        BENCHMARK("any_threatens for exactly 12 zombies, all bounded routes blocked") {
            calendar::turn += 1_turns;
            return smart_safemode::any_threatens(bounded, you);
        };
        BENCHMARK("any_threatens for 100 zombies, conservative budget stop without routes") {
            calendar::turn += 1_turns;
            return smart_safemode::any_threatens(seen, you);
        };
    }
}

TEST_CASE("monster info update with a horde in sight", "[.][benchmark][smart_safemode]") {
    const auto restore_turn = restore_on_out_of_scope<time_point>(calendar::turn);
    const auto cleanup = on_out_of_scope([] { clear_all_state(); });
    const auto center = prepare_daylight_field();
    spawn_horde(center, 100);
    // Reinforced glass: the horde stays in sight but has no route, the slowest case.
    wall_in(center, ter_id("t_reinforced_glass"));
    auto& here = get_map();
    here.build_map_cache(center.z());
    here.update_visibility_cache(center.z());
    const auto update = [] {
        calendar::turn += 1_turns;
        g->mon_info_update();
        return get_avatar().get_mon_visible().new_seen_mon.size();
    };

    SECTION("smart safe mode and edge arrows off") {
        const override_option smart("SMART_SAFEMODE", "false");
        const override_option arrows("ENEMY_EDGE_ARROWS", "false");
        BENCHMARK("steady mon_info_update, 100 zombies, smart features off") { return update(); };
    }
    SECTION("smart safe mode and edge arrows on") {
        const override_option smart("SMART_SAFEMODE", "true");
        const override_option arrows("ENEMY_EDGE_ARROWS", "true");
        BENCHMARK("steady mon_info_update, 100 zombies, smart features on") { return update(); };
        BENCHMARK("steady monster scan plus fresh-turn edge-arrow routes, 100 zombies") {
            update();
            return enemy_indicators::map_arrows(get_avatar(), 21, 11).size();
        };
    }
}

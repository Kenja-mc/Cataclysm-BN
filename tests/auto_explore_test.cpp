#include "action.h"
#include "auto_explore.h"
#include "avatar.h"
#include "catch/catch.hpp"
#include "map/map.h"
#include "player_activity.h"
#include "state_helpers.h"
#include "type_id.h"

#include <functional>
#include <optional>

namespace {

using known_fn = std::function<auto(const tripoint_bub_ms&)->bool>;

/// The player knows every tile within `radius` steps of `centre` and nothing else.
auto known_within(const tripoint_bub_ms& centre, const int radius) -> known_fn {
    return [centre, radius](const tripoint_bub_ms& p) { return square_dist(centre, p) <= radius; };
}

/// Walls every tile exactly `radius` steps from `centre`, except `gap`.
auto wall_ring(
    map& here, const tripoint_bub_ms& centre, const int radius,
    const std::optional<tripoint_bub_ms>& gap) -> void {
    for (const auto& p : here.points_in_radius(centre, radius)) {
        if (square_dist(centre, p) == radius && p != gap) {
            here.ter_set(p, ter_str_id("t_wall").id());
        }
    }
}

} // namespace

TEST_CASE("auto_explore_picks_the_nearest_tile_bordering_unknown_ground", "[auto_explore]") {
    clear_all_state();
    auto& you = get_avatar();
    auto& here = get_map();
    const auto start = you.bub_pos();

    const auto target = auto_explore::nearest_frontier(
        {.you = you, .here = here, .is_known = known_within(start, 5)});

    REQUIRE(target.has_value());
    CHECK(square_dist(start, *target) == 5);
}

TEST_CASE("auto_explore_does_not_see_through_walls", "[auto_explore]") {
    clear_all_state();
    auto& you = get_avatar();
    auto& here = get_map();
    const auto start = you.bub_pos();

    SECTION("a sealed room has no frontier") {
        wall_ring(here, start, 2, std::nullopt);
        CHECK_FALSE(
            auto_explore::nearest_frontier(
                {.you = you, .here = here, .is_known = known_within(start, 5)})
                .has_value());
    }

    SECTION("a gap in the wall leads to the frontier outside") {
        const auto gap = start + tripoint(2, 0, 0);
        wall_ring(here, start, 2, gap);
        const auto target = auto_explore::nearest_frontier(
            {.you = you, .here = here, .is_known = known_within(start, 5)});
        REQUIRE(target.has_value());
        CHECK(square_dist(start, *target) == 5);
        CHECK_FALSE(
            here.route(start, *target, you.get_legacy_pathfinding_settings(),
                       you.get_legacy_path_avoid())
                .empty());
    }
}

TEST_CASE("auto_explore_stops_when_everything_is_known", "[auto_explore]") {
    clear_all_state();
    auto& you = get_avatar();
    auto& here = get_map();

    CHECK_FALSE(
        auto_explore::nearest_frontier(
            {.you = you, .here = here, .is_known = [](const tripoint_bub_ms&) { return true; }})
            .has_value());
    CHECK_FALSE(auto_explore::set_route_to_frontier(
        {.you = you, .here = here, .is_known = [](const tripoint_bub_ms&) { return true; }}));
    CHECK_FALSE(you.has_destination());
}

TEST_CASE("auto_explore_route_is_walkable_by_the_auto_move_loop", "[auto_explore]") {
    clear_all_state();
    auto& you = get_avatar();
    auto& here = get_map();
    const auto start = you.bub_pos();
    const auto known = known_within(start, 5);

    const auto target = auto_explore::nearest_frontier(
        {.you = you, .here = here, .is_known = known});
    REQUIRE(target.has_value());
    REQUIRE(auto_explore::set_route_to_frontier({.you = you, .here = here, .is_known = known}));

    REQUIRE(you.has_destination());
    CHECK(you.get_auto_move_route().back() == *target);
    // The main loop asks for the next step from the player's current tile; a route whose first
    // step was already consumed would cancel here.
    CHECK(you.get_next_auto_move_direction() != ACTION_NULL);
    you.clear_destination();
}

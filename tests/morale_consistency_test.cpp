#include "avatar.h"
#include "calendar.h"
#include "catch/catch.hpp"
#include "debug.h"
#include "item.h"
#include "morale.h"
#include "morale_types.h"
#include "npc.h"
#include "player_helpers.h"
#include "type_id.h"

TEST_CASE("dumped_clothing_drops_stylish_morale", "[morale]") {
    avatar& you = get_avatar();
    clear_avatar();
    REQUIRE_FALSE(static_cast<bool>(you.wear_item(item::spawn("dress_shoes"), false)));
    REQUIRE(you.get_morale(MORALE_PERM_FANCY) > 0);

    // `drop_all_items` and death both empty worn through inv_dump_remove; the takeoff
    // notifications that shed the worn morale must run for each of those items.
    const auto dumped = you.inv_dump_remove();
    REQUIRE(dumped.size() == 1); // the dress shoes, and nothing else from a cleared avatar
    REQUIRE(you.get_morale(MORALE_PERM_FANCY) == 0);

    const auto dmsg = capture_debugmsg_during([&]() { CHECK(you.check_and_recover_morale()); });
    CHECK(dmsg.empty());
}

TEST_CASE("clearing_morale_keeps_derived_stylish_bonus", "[morale]") {
    avatar& you = get_avatar();
    clear_avatar();
    REQUIRE_FALSE(static_cast<bool>(you.wear_item(item::spawn("dress_shoes"), false)));
    REQUIRE(you.get_morale(MORALE_PERM_FANCY) > 0);

    // The harness clears morale while items stay worn; the worn bonus is derived state and
    // must be rebuilt, or the next consistency check reports it as missing.
    you.clear_morale();
    REQUIRE(you.get_morale(MORALE_PERM_FANCY) > 0);

    const auto dmsg = capture_debugmsg_during([&]() { CHECK(you.check_and_recover_morale()); });
    CHECK(dmsg.empty());
}

TEST_CASE("player_morale_from_effects_consistent", "[morale][effect][slow]") {
    npc dummy;
    dummy.add_effect(efftype_id("test_high"), 1_minutes);
    const time_point start = calendar::turn_zero;
    const time_point end = start + 2_minutes;
    const time_duration tick_size = 1_turns;
    // As in game::do_turn
    for (time_point t = start; t < end; t += tick_size) {
        dummy.process_turn();
        dummy.process_items();
        if (to_turns<int>(t - start) % to_turns<int>(10_turns) == 0) { dummy.update_morale(); }
        if (to_turns<int>(t - start) % to_turns<int>(9_turns) == 0) {
            REQUIRE(dummy.check_and_recover_morale());
        }
    }
}

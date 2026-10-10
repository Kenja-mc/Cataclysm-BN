#include "cata_utility.h"
#include "catch/catch.hpp"
#include "debug.h"
#include "filesystem.h"
#include "game.h"
#include "item.h"
#include "json.h"
#include "stack_modifier.h"
#include "state_helpers.h"
#include "world.h"
#include "worldfactory.h"

#include <filesystem>
#include <sstream>
#include <string>

namespace fs = std::filesystem;

TEST_CASE("failed save load blocks saving over the broken save", "[save][load]") {
    clear_all_state();
    g->clear_failed_load_save_block();
    const auto cleanup = on_out_of_scope([]() {
        clear_all_state();
        g->clear_failed_load_save_block();
    });

    const auto fixture_path = fs::path("tests/data/save/broken_load_save/#QnJva2VuU2F2ZQ==.sav");
    const auto world_path = fs::path(g->get_active_world()->info->folder_path());
    const auto save_path = world_path / "#QnJva2VuU2F2ZQ==.sav";
    CHECK(fs::copy_file(fixture_path, save_path, fs::copy_options::overwrite_existing));

    const auto before_load = read_entire_file(save_path.string());
    auto loaded = true;
    const auto debug_message = capture_debugmsg_during([&]() {
        loaded = g->load(save_t::from_save_id("BrokenSave"));
    });

    CHECK_FALSE(loaded);
    CHECK(debug_message.find("Bad save json") != std::string::npos);
    CHECK_FALSE(g->save(false));
    CHECK(read_entire_file(save_path.string()) == before_load);
}

TEST_CASE("manual combat mode is serialized in save data", "[save]") {
    clear_all_state();
    const auto cleanup = on_out_of_scope([]() { clear_all_state(); });

    g->manual_combat_mode = true;

    std::ostringstream save_data;
    g->serialize(save_data);

    CHECK(save_data.str().find(R"("manual_combat_mode": true)") != std::string::npos);
}

TEST_CASE("old_save_revolver_keeps_black_powder_rounds", "[save][migration]") {
    const auto load = [](item& it, const std::string& json) {
        auto iss = std::istringstream(json);
        auto jsin = JsonIn(iss);
        it.deserialize(jsin);
    };
    const auto black_powder = stack_modifier_id("black_powder");
    auto gun = item();

    SECTION("loaded rounds keep the modifier") {
        load(gun, R"({"typeid": "sw_619", "curammo": "bp_38_special", "charges": 6})");
        CHECK(gun.ammo_current() == itype_id("38_special"));
        CHECK(stack_modifiers::count(gun, black_powder) == 6);
    }
    SECTION("an empty gun gets no modified rounds") {
        load(gun, R"({"typeid": "sw_619", "curammo": "bp_38_special", "charges": 0})");
        CHECK(stack_modifiers::count(gun, black_powder) == 0);
    }
}

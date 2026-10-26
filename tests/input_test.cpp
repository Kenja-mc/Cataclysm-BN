#include "catch/catch.hpp"
#include "filesystem.h"
#include "game.h"
#include "input.h"
#include "options_helpers.h"
#include "path_info.h"

#include <algorithm>
#include <fstream>
#include <iterator>
#include <map>
#include <string>
#include <vector>

namespace {

class user_keybindings_file_guard {
public:
    ~user_keybindings_file_guard() {
        remove_file(PATH_INFO::user_keybindings());
        inp_mngr.init();
    }
};

auto write_user_keybindings(const std::string& entry) -> void {
    auto file = std::ofstream(PATH_INFO::user_keybindings(), std::ios::binary);
    REQUIRE(file.good());
    file << "[\n" << entry << "\n]\n";
}

auto read_user_keybindings() -> std::string {
    auto file = std::ifstream(PATH_INFO::user_keybindings(), std::ios::binary);
    REQUIRE(file.good());
    return {std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>()};
}

auto npc_trade_right_keys() -> std::vector<char> {
    auto ctxt = input_context("NPC_TRADE");
    return ctxt.keys_bound_to("RIGHT");
}

auto contains_key(const std::vector<char>& keys, const char key) -> bool {
    return std::ranges::find(keys, key) != keys.end();
}

/// Keyboard inputs that trigger more than one action registered in the main game, each with
/// the actions it triggers.
auto main_game_key_clashes() -> std::map<std::vector<int>, std::vector<std::string>> {
    auto ctxt = get_default_mode_input_context();
    auto actions_by_key = std::map<std::vector<int>, std::vector<std::string>>();
    for (const auto& action : ctxt.get_registered_actions_copy()) {
        for (const auto& event : inp_mngr.get_input_for_action(action, "DEFAULTMODE")) {
            if (event.type == input_event_t::keyboard) {
                auto& actions = actions_by_key[event.sequence];
                if (!std::ranges::contains(actions, action)) { actions.push_back(action); }
            }
        }
    }
    std::erase_if(actions_by_key, [](const auto& entry) { return entry.second.size() < 2; });
    return actions_by_key;
}

auto describe(const std::map<std::vector<int>, std::vector<std::string>>& clashes) -> std::string {
    auto out = std::string();
    for (const auto& [keys, actions] : clashes) {
        out += inp_mngr.get_keyname(keys.front(), input_event_t::keyboard) + ":";
        for (const auto& action : actions) { out += " " + action; }
        out += "\n";
    }
    return out;
}

} // namespace

// The classic scheme keeps upstream's bindings, clashes included (h and w also open the guide
// and the wiki there), so only the modern scheme is held to this.
TEST_CASE("no key triggers two main game actions in the modern scheme", "[input][keybindings]") {
    auto restore_keybindings = user_keybindings_file_guard();
    auto modern = override_option("CONTROL_SCHEME", "modern");
    inp_mngr.init();
    const auto clashes = main_game_key_clashes();
    INFO(describe(clashes));
    CHECK(clashes.empty());
}

TEST_CASE("deleted local keybindings fall back to global bindings", "[input][keybindings]") {
    auto restore_keybindings = user_keybindings_file_guard();

    write_user_keybindings(R"({
  "type": "keybinding",
  "id": "RIGHT",
  "category": "NPC_TRADE",
  "bindings": []
})");
    inp_mngr.init();

    auto keys = npc_trade_right_keys();
    CHECK(keys.empty());

    write_user_keybindings(R"({
  "type": "keybinding",
  "id": "RIGHT",
  "category": "NPC_TRADE",
  "is_deleted": true,
  "bindings": []
})");
    inp_mngr.init();

    keys = npc_trade_right_keys();
    CHECK(contains_key(keys, 'l'));
    CHECK(contains_key(keys, '6'));

    inp_mngr.save();
    CHECK(read_user_keybindings().find("\"is_deleted\": true") != std::string::npos);
}

TEST_CASE("manual combat default bindings reserve backtab for the toggle", "[input][keybindings]") {
    const auto autoattack_key = inp_mngr.get_first_char_for_action("autoattack", "DEFAULTMODE");
    const auto toggle_key = inp_mngr.get_first_char_for_action(
        "toggle_manual_combat_mode",
        "DEFAUL"
        "TMOD"
        "E");
    const auto removed_manual_attack_key = inp_mngr.get_first_char_for_action(
        "manual_attack",
        "DEF"
        "AUL"
        "TMO"
        "D"
        "E");

    CHECK(autoattack_key == inp_mngr.get_keycode("TAB"));
    CHECK(toggle_key == inp_mngr.get_keycode("BACKTAB"));
    CHECK(removed_manual_attack_key == 0);
}

TEST_CASE(
    "a modern-scheme rebind to the upstream key survives save and reload", "[input][keybindings]") {
    auto restore_keybindings = user_keybindings_file_guard();
    auto modern = override_option("CONTROL_SCHEME", "modern");
    const auto pickup_keys = [] {
        return input_context("DEFAULTMODE").keys_bound_to("pickup_all", false);
    };
    const auto user_pickup_comma = std::string(R"({
  "type": "keybinding",
  "id": "pickup_all",
  "category": "DEFAULTMODE",
  "bindings": [ { "input_method": "keyboard", "key": "," } ]
})");

    SECTION("files with the format marker keep the binding") {
        write_user_keybindings(
            R"({ "type": "keybindings_format", "version": 2 },)" + user_pickup_comma);
        inp_mngr.init();
        REQUIRE(contains_key(pickup_keys(), ','));

        inp_mngr.save();
        inp_mngr.init();
        CHECK(contains_key(pickup_keys(), ','));
        CHECK_FALSE(contains_key(pickup_keys(), inp_mngr.get_keycode("CTRL+G")));
    }

    SECTION("older files that repeat the upstream default follow the scheme") {
        inp_mngr.init();
        // The scheme decides the key, so read its default instead of naming one.
        const auto scheme_default = pickup_keys();
        write_user_keybindings(user_pickup_comma);
        inp_mngr.init();
        CHECK(pickup_keys() == scheme_default);
        CHECK_FALSE(contains_key(pickup_keys(), ','));
    }
}

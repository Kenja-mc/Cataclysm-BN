"""Built-in tutorial text must describe routes a player can actually follow."""
import json
import re
from pathlib import Path

from aim_reticle import action_clock
from helpers import HELPERS, arena, bub_pos, count_carried, empty_inventory, spawn, wait_until
from inventory_mouse import row_of
from playtest import start_tutorial
from tmux_game import Game


SNIPPETS = {entry["id"]: entry["text"]
            for group in json.loads(Path("data/json/snippets/tutorial.json").read_text())
            for entry in group["text"]}


def lesson_prefix(lesson, scheme):
    modern = lesson + "_MODERN"
    source = SNIPPETS[modern if scheme == "modern" and modern in SNIPPETS else lesson]
    # An anchor from the data, not a second copy of tutorial prose in the test.
    return source.split("<", 1)[0][:32].rstrip()


def lesson(game, name, scheme):
    game.wait_for(lesson_prefix(name, scheme))
    screen = game.screen()
    assert "<press_" not in screen and "(unbound)" not in screen, \
        "tutorial routes must expand to usable input or menus:\n" + screen
    return screen


def close_lesson(game, name, scheme):
    game.keys("space", delay=0.2)
    game.wait_gone(lesson_prefix(name, scheme))


def exercise_initial_and_door_lessons(scheme):
    game = Game(name="bn-e2e-tutorial-" + scheme, cols=174, rows=45, options={
        "CONTROL_SCHEME": scheme, "SAFEMODE": "false", "SHOW_WELCOME": "false",
        "SHOW_TIPS": "false", "CONTEXTUAL_INTERACT": "true", "MOUSE_MOVE": "false",
        "AUTOSELECT_SINGLE_VALID_TARGET": "false"})
    try:
        start_tutorial(game)
        # Tutorials present per-turn lessons only once the first real action runs.
        if lesson_prefix("LESSON_INTRO", scheme) not in game.screen():
            game.keys("x" if scheme == "modern" else ".", delay=0.2)
        lesson(game, "LESSON_INTRO", scheme)
        close_lesson(game, "LESSON_INTRO", scheme)
        movement = lesson(game, "LESSON_MOVE", scheme)
        for key in ("w", "a", "s", "d") if scheme == "modern" else ("k", "h", "j", "l"):
            assert re.search(r"\b" + key + r"\b", movement), \
                "the lesson must name the active scheme's movement keys:\n" + movement
        close_lesson(game, "LESSON_MOVE", scheme)
        looking = lesson(game, "LESSON_LOOK", scheme)
        if scheme == "modern":
            assert "Shift" in looking and "right-click" in looking, looking
        else:
            assert ";" in looking and "right-click" not in looking, looking
        close_lesson(game, "LESSON_LOOK", scheme)
        lesson(game, "LESSON_RECOIL", scheme)
        close_lesson(game, "LESSON_RECOIL", scheme)
        pickup = lesson(game, "LESSON_PICKUP", scheme)
        if scheme == "modern":
            assert re.search(r"\bg\b", pickup), pickup
        close_lesson(game, "LESSON_PICKUP", scheme)
        game.define_lua(HELPERS)
        empty_inventory(game)
        arena(game)
        position = bub_pos(game)
        game.keys("d" if scheme == "modern" else "l", delay=0.2)
        assert bub_pos(game) == (position[0] + 1, position[1], position[2]), \
            "the movement lesson's ordinary movement key must really move"
        assert game.lua("M:set_ter_at(here(1,0),TerId.new('t_door_c'):int_id()) out('ok')") == ["ok"]
        game.keys("x" if scheme == "modern" else ".", delay=0.2)
        opening = lesson(game, "LESSON_OPEN", scheme)
        key = "Space" if scheme == "modern" else "o"
        assert re.search(r"\b" + key + r"\b", opening), opening
        close_lesson(game, "LESSON_OPEN", scheme)
        position, clock = bub_pos(game), action_clock(game)
        if scheme == "modern":
            x, y = game.find("@")
            game.click(x + 1, y)
        else:
            game.keys("o", "l", delay=0.2)
        closing = lesson(game, "LESSON_CLOSE", scheme)
        key = "Space" if scheme == "modern" else "c"
        assert re.search(r"\b" + key + r"\b", closing), closing
        close_lesson(game, "LESSON_CLOSE", scheme)
        assert game.lua("out(M:get_ter_at(here(1,0)):str_id():str())") == ["t_door_o"]
        assert bub_pos(game) == position and action_clock(game) > clock
        clock = action_clock(game)
        if scheme == "modern":
            # Follow the alternative taught route: select, Space, then the close choice.
            game.keys("D", "space", delay=0.2)
            game.wait_for("Interact with the")
            game.keys("c", delay=0.2)
            # Space is Examine even when its contextual choice closes a door.
            # Its post-action lesson is distinct from a direct click's Close lesson.
            interaction = lesson(game, "LESSON_INTERACT", scheme)
            assert "Space" in interaction, interaction
            close_lesson(game, "LESSON_INTERACT", scheme)
            assert game.lua("out(M:get_ter_at(here(1,0)):str_id():str())") == ["t_door_c"]
            assert bub_pos(game) == position and action_clock(game) > clock
            # Follow the other taught close route too, without changing the fixture:
            # reopen the real door, then click it closed to trigger the smash lesson.
            x, y = game.find("@")
            game.click(x + 1, y)
            assert game.lua("out(M:get_ter_at(here(1,0)):str_id():str())") == ["t_door_o"]
            assert bub_pos(game) == position
            clock = action_clock(game)
            x, y = game.find("@")
            game.click(x + 1, y)
        else:
            game.keys("c", "l", delay=0.2)
        lesson(game, "LESSON_SMASH", scheme)
        close_lesson(game, "LESSON_SMASH", scheme)
        assert game.lua("out(M:get_ter_at(here(1,0)):str_id():str())") == ["t_door_c"]
        assert bub_pos(game) == position and action_clock(game) > clock
        return game
    except BaseException:
        game.close()
        raise


def exercise_container_ammo_lesson(game, scheme, spare_capacity):
    arena(game)
    # Seed a real ammo container, then let pickup transfer the ground stack into it.
    capacity = int(game.lua(
        "local a=gapi.get_avatar() "
        "TUTORIAL_AMMO_POUCH=a:create_item(ItypeId.new('ammo_pouch'),-1) "
        "local capacity=TUTORIAL_AMMO_POUCH:ammo_capacity(false) "
        f"TUTORIAL_AMMO_POUCH:add_item_with_id(ItypeId.new('9mm'),capacity-{spare_capacity}) "
        "M:create_item_at(here(0,0),ItypeId.new('9mm'),3) out(capacity)")[0])
    assert capacity > spare_capacity
    pickup_key = "g" if scheme == "modern" else ","
    game.keys(pickup_key, delay=0.2)
    game.wait_for("Pick up")
    # Merely opening/canceling pickup must not teach a successful acquisition.
    game.keys("Escape", delay=0.2)
    game.wait_gone("Pick up")
    assert lesson_prefix("LESSON_GOT_AMMO", scheme) not in game.screen()
    assert game.lua("out(TUTORIAL_AMMO_POUCH:ammo_remaining())") == [str(capacity - spare_capacity)]
    assert count_carried(game, "9mm") == capacity - spare_capacity
    game.keys(pickup_key, delay=0.2)
    game.wait_for("Pick up")
    game.keys(",", "Enter", delay=0.2)
    lesson(game, "LESSON_GOT_AMMO", scheme)
    close_lesson(game, "LESSON_GOT_AMMO", scheme)
    game.wait_gone("Pick up")
    assert game.lua("out(TUTORIAL_AMMO_POUCH:ammo_remaining())") == [str(capacity)]
    assert count_carried(game, "9mm") == capacity - spare_capacity + 3, \
        "full and partial container transfers must preserve the real acquired charges"
    assert game.lua("out(#M:get_items_at(here(0,0)))") == ["0"]


def test_modern_tutorial_routes_are_reachable(_g):
    game = exercise_initial_and_door_lessons("modern")
    try:
        arena(game)
        spawn(game, 0, 0, "flashlight")
        assert game.lua("for _,it in pairs(M:get_items_at(here(0,0))) do "
                        "it:ammo_set(ItypeId.new('battery'),100) end out('ok')") == ["ok"]
        game.keys("g", delay=0.2)
        game.wait_for("Pick up")
        game.keys("g", delay=0.2)
        tool = lesson(game, "LESSON_GOT_TOOL", "modern")
        assert "→" in tool and "item" in tool and "Activate" in tool, \
            "an unbound apply key must teach the existing item action route:\n" + tool
        close_lesson(game, "LESSON_GOT_TOOL", "modern")
        assert count_carried(game, "flashlight") == 1
        game.keys("i", delay=0.2)
        game.wait_for("Item hotkeys assigned")
        game.wait_for("flashlight")
        game.click(*row_of(game, "flashlight"), button=2)
        game.wait_for("Activate")
        game.keys("A", delay=0.2)
        game.wait_gone("Item hotkeys assigned")
        game.wait_gone("Activate")
        assert wait_until(lambda: game.lua(
            "local active=false for _,it in ipairs(gapi.get_avatar():all_items(false)) do "
            "if it:get_type():str()=='flashlight_on' then active=it:is_active() end end out(active)") == ["true"]), \
            "the tutorial's inventory activation route must turn the real light on:\n" + game.screen()
        # Only one of the three rounds fits; the live remainder is then stashed.
        exercise_container_ammo_lesson(game, "modern", spare_capacity=1)
    finally:
        game.close()


def test_classic_tutorial_preserves_classic_controls(_g):
    game = exercise_initial_and_door_lessons("classic")
    try:
        # All three rounds merge, destroying the source and redirecting its safe reference.
        exercise_container_ammo_lesson(game, "classic", spare_capacity=3)
    finally:
        game.close()


TESTS = [test_modern_tutorial_routes_are_reachable,
         test_classic_tutorial_preserves_classic_controls]

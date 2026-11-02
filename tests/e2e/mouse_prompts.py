from concurrent.futures import ThreadPoolExecutor

from contextual_hub import contextual_game
from helpers import bub_pos, count_at, spawn, wait_until


def examine_prompt(game, key):
    spawn(game, 1, 0, "rock")
    spawn(game, -1, 0, "stick")
    game.keys(key, delay=0.5)
    game.wait_for("Examine where?")


def test_click_answers_a_direction_prompt(_g):
    with contextual_game("bn-e2e-mouse-direction", CONTEXTUAL_INTERACT="false") as game:
        position = bub_pos(game)
        examine_prompt(game, "space")
        assert "(Direction button or click)" in game.screen(), game.screen()
        x, y = game.find("@")
        game.click(x + 1, y)
        assert wait_until(lambda: "Pick up" in game.screen() and "rock" in game.screen(), 10), \
            "a click beside the avatar must answer the prompt with that tile:\n" + game.screen()
        assert "stick" not in game.screen(), "the other neighbour must not be examined:\n" + game.screen()
        game.keys("Escape", delay=0.6)
        game.wait_gone("Pick up")
        assert count_at(game, -1, 0, "stick") == 1, "the other neighbour must keep its item"
        assert bub_pos(game) == position, "answering by click must not walk"


def test_classic_direction_prompt_ignores_clicks(_g):
    with contextual_game("bn-e2e-mouse-direction-classic", CONTROL_SCHEME="classic") as game:
        examine_prompt(game, "e")
        assert "(Direction button)" in game.screen(), game.screen()
        x, y = game.find("@")
        game.click(x + 1, y)
        assert "Examine where?" in game.screen(), "Classic keeps upstream's keyboard-only prompt"
        game.keys("Escape", delay=0.5)


def button_cell(game, label):
    for y, line in enumerate(game.screen().splitlines()):
        if "(Y)es" in line and "(N)o" in line:
            return line.index("(N)o" if label == "No" else "(Y)es") + 1, y
    raise AssertionError("no Yes/No button row:\n" + game.screen())


def test_popup_button_follows_hover(_g):
    with contextual_game("bn-e2e-mouse-popup-hover") as game:
        for label, expected in (("No", "NO"), ("Yes", "YES")):
            with ThreadPoolExecutor(max_workers=1) as executor:
                result = executor.submit(game.lua,
                                         "local p=QueryPopup.new() p:message('Hover test') out(p:query_yn())")
                assert wait_until(lambda: "Hover test" in game.screen() and "Ctrl+S" not in game.screen()
                                  and "Yes" in game.screen(), 20), game.screen()
                game.hover(*button_cell(game, label))
                game.keys("Enter", delay=0.5)
                assert result.result() == [expected], \
                    f"Enter must confirm the hovered {label} button:\n" + game.screen()


def test_click_selects_a_row_in_a_categorized_menu(_g):
    import json, tempfile
    from pathlib import Path
    bindings = Path(tempfile.mkdtemp()) / "keybindings.json"
    bindings.write_text(json.dumps([{"id": "cast_spell", "category": "DEFAULTMODE",
                                     "bindings": [{"input_method": "keyboard", "key": "F9"}]}]))
    with contextual_game("bn-e2e-mouse-category", keybindings=str(bindings)) as game:
        assert game.lua("local a=gapi.get_avatar() a:get_magic():learn_spell(SpellTypeId.new('debug_hp'),a,true) "
                        "out('ok')") == ["ok"]
        game.keys("F9", delay=0.8)
        game.wait_for("Debug HP Spell")
        game.keys("*", delay=0.4)
        game.wait_for("*b Debug HP Spell")
        game.click(*game.find("<<"))
        assert wait_until(lambda: "<< Favorites >>" in game.screen(), 10), \
            f"the category label click must cycle the filter:\n{game.screen()}"
        game.click(*game.find("<<"))
        game.wait_for("Debug HP Spell")
        game.click(*game.find("Debug HP Spell"))
        assert wait_until(lambda: game.lua("out(gapi.get_avatar():get_activity() ~= nil)") == ["true"],
                          10), f"a row click must select the spell:\n{game.screen()}"

TESTS = [test_click_answers_a_direction_prompt, test_classic_direction_prompt_ignores_clicks,
         test_popup_button_follows_hover, test_click_selects_a_row_in_a_categorized_menu]

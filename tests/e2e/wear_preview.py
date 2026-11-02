"""The Wear menu previews the encumbrance an item would add before it is worn."""
import re

from fixtures import shared_game
from helpers import HELPERS, arena, empty_inventory, give, wait_until

OPTIONS = {"CONTROL_SCHEME": "classic", "SAFEMODE": "false"}


def fresh(game):
    empty_inventory(game)
    arena(game)


def worn(game, item):
    return game.lua("local a=gapi.get_avatar() local n=0 "
                    "for _,it in ipairs(a:get_worn_items()) do "
                    f"if it:get_type():str()=='{item}' then n=n+1 end end out(n)")[0] == "1"


def wear_from_pack(game, item):
    """Wear one carried item without the menu, leaving the rest for the Wear menu."""
    out = game.lua("local a=gapi.get_avatar() local done=false "
                   "for _,it in ipairs(a:all_items(false)) do "
                   f"if it:get_type():str()=='{item}' and not a:is_wearing(it) then "
                   "assert(a:wear(it,false)) done=true break end end "
                   "out(done and 'ok' or 'missing')")
    assert out == ["ok"], out


def torso_preview(game):
    match = re.search(r"Torso\s+(\d+)\s*→\s*(\d+)", game.screen())
    assert match, f"the preview must show the torso before and after:\n{game.screen()}"
    return int(match.group(1)), int(match.group(2))


def test_wear_menu_previews_layering_and_the_armor_screen_agrees(_g):
    with shared_game("bn-e2e-wear-preview", options=OPTIONS, define=HELPERS,
                     setup=fresh) as game:
        give(game, "hoodie")
        give(game, "jacket_leather")
        wear_from_pack(game, "hoodie")
        arena(game)

        game.keys("W", delay=1.0)
        game.wait_for("Wear item", timeout=10)
        game.settle_screen()
        screen = game.screen()
        assert "leather jacket" in screen, screen
        assert "with hoodie" in screen, f"the preview must name what it layers over:\n{screen}"
        before, after = torso_preview(game)
        assert before > 0, f"the worn hoodie must already add encumbrance:\n{screen}"
        assert after > before, f"a second outer layer must add encumbrance:\n{screen}"

        game.keys("Enter", delay=1.2)
        game.wait_gone("Wear item", timeout=10)
        assert wait_until(lambda: worn(game, "jacket_leather")), game.screen()

        game.keys("+", delay=1.0)
        game.wait_for("Sort Armor", timeout=10)
        armor = game.screen()
        row = re.search(r"Torso\s+(\d+)\s*\+\s*(-?\d+)", armor)
        assert row, f"the armor screen must list the torso encumbrance:\n{armor}"
        assert int(row.group(1)) + int(row.group(2)) == after, \
            f"the armor screen must agree with the preview's {after}:\n{armor}"
        game.keys("Escape", delay=0.5)
        game.wait_gone("Sort Armor", timeout=10)

        empty_inventory(game)
        arena(game)


def test_wear_menu_says_when_nothing_changes(_g):
    with shared_game("bn-e2e-wear-preview", options=OPTIONS, define=HELPERS,
                     setup=fresh) as game:
        give(game, "gloves_light_fingerless")
        arena(game)

        game.keys("W", delay=1.0)
        game.wait_for("Wear item", timeout=10)
        game.settle_screen()
        assert "No encumbrance change" in game.screen(), game.screen()
        game.keys("Escape", delay=0.5)

        empty_inventory(game)
        arena(game)


TESTS = [test_wear_menu_previews_layering_and_the_armor_screen_agrees,
         test_wear_menu_says_when_nothing_changes]

import json
from pathlib import Path

from fixtures import shared_game
from helpers import HELPERS, arena, settle

ROOT = Path(__file__).resolve().parents[2]
SCHEME = ROOT / "data" / "raw" / "control_schemes" / "modern.json"
BASE = ROOT / "data" / "raw" / "keybindings" / "keybindings.json"

TABS = ("1 Missions", "2 Factions", "3 Zones", "4 Scores")
STRIP = "<│1 Missions│>"
PLAY_ROW = "X,Y,Z"
COLS, ROWS, SIDEBAR = 140, 45, 44


def tab_strip(tab):
    return f"<│{tab}│>"


def assert_page_closed(game):
    for tab in TABS:
        assert tab_strip(tab) not in game.screen(), (
            "the World page must be closed:\n" + game.screen())


def world_game():
    return shared_game("bn-e2e-world-hub", define=HELPERS, setup=arena,
                       options={"CONTROL_SCHEME": "modern", "SAFEMODE": "false"})


def open_page(game):
    game.keys("M", delay=0.8)
    game.wait_for(STRIP)
    return game.screen()


def show_tab(game, number, tab, content):
    game.keys(number, delay=0.7)
    game.wait_for(f"<│{tab}│>")
    game.wait_for(content)


def keybindings(path):
    return {e["id"]: e for e in json.loads(path.read_text()) if e.get("type") == "keybinding"}


def keyboard_keys(entry):
    return {b["key"] for b in entry.get("bindings", ()) if b["input_method"] == "keyboard"}


def test_world_screens_stay_bindable_without_plain_marker_keys(_g):
    modern = keybindings(SCHEME)
    for action in ("missions", "factions", "zones", "scores"):
        assert action in modern, f"{action} must stay a bindable action"
    marker_keys = {"z", "x", "c", "v"}
    for action in ("world_hub", "missions", "factions", "zones", "scores"):
        keys = keyboard_keys(modern[action])
        assert not keys & marker_keys, (
            f"{action} must not take a map-marker letter, got {sorted(keys)}")
    assert keyboard_keys(modern["world_hub"]) == {"M"}
    base = keybindings(BASE)
    for action in ("ADD_ZONE", "REMOVE_ZONE", "MOVE_ZONE_UP", "MOVE_ZONE_DOWN",
                   "SHOW_ZONE_ON_MAP", "ENABLE_ZONE", "DISABLE_ZONE", "SHOW_ALL_ZONES",
                   "TOGGLE_ZONE_OVERLAY", "SWAPTONPC"):
        keys = keyboard_keys(base[action])
        assert not keys & marker_keys, (
            f"{action} must not take a map-marker letter, got {sorted(keys)}")
    for action in ("ADD_ZONE", "DISABLE_ZONE", "SHOW_ALL_ZONES"):
        keys = keyboard_keys(modern[action])
        assert not keys & marker_keys, (
            f"{action} must not take a map-marker letter, got {sorted(keys)}")
    assert "M" in keyboard_keys(base["missions"]), "Classic must keep its own missions key"
    assert "world_hub" in base, "world_hub needs a keybindings entry for Classic and the menu"
    assert base["world_hub"]["name"] == "World"
    assert keyboard_keys(base["world_hub"]) == set(), "Classic leaves the World page unbound"


def test_world_page_draws_tab_content_inline(_g):
    with world_game() as game:
        settle(game)
        screen = open_page(game)
        assert "ACTIVE MISSIONS" in screen, "the first tab must show mission content:\n" + screen
        for label in ("2 Factions", "3 Zones", "4 Scores"):
            assert label in screen, "the page must number every tab:\n" + screen
        assert "returns to play" in screen, "the page must say how to leave:\n" + screen

        for key in ("z", "x", "c", "v"):
            game.keys(key, delay=0.3)
        assert STRIP in game.screen(), "z/x/c/v must not switch or leave the page:\n" + game.screen()

        game.keys("?", delay=0.8)
        game.wait_for("Keybindings")
        game.keys("Escape", delay=0.6)
        game.wait_gone("Keybindings")
        game.wait_for(STRIP)

        show_tab(game, "4", "4 Scores", "ACHIEVEMENTS")
        show_tab(game, "2", "2 Factions", "YOUR FOLLOWERS")
        show_tab(game, "3", "3 Zones", "Zones (")
        show_tab(game, "1", "1 Missions", "ACTIVE MISSIONS")

        game.keys("Escape", delay=0.6)
        game.wait_gone(STRIP)
        assert_page_closed(game)
        game.wait_for(PLAY_ROW)


def test_world_page_reaches_the_zone_actions(_g):
    with world_game() as game:
        settle(game)
        open_page(game)
        game.keys("3", delay=0.7)
        game.wait_for("<│3 Zones│>")
        game.wait_for("Zones (")

        game.keys("A", delay=0.8)
        game.wait_for("Select zone type:")
        game.keys("Escape", delay=0.6)
        game.wait_gone("Select zone type:")
        game.wait_for("Zones (")

        game.keys("S", delay=0.6)
        game.wait_for("showing every zone")
        game.keys("S", delay=0.6)
        game.wait_for("showing zones nearby")

        game.keys("Escape", delay=0.6)
        game.wait_gone(tab_strip("3 Zones"))
        assert_page_closed(game)
        game.wait_for(PLAY_ROW)


def test_classic_direct_keys_still_open_their_screens(_g):
    with shared_game("bn-e2e-world-hub-classic", define=HELPERS, setup=arena,
                     options={"CONTROL_SCHEME": "classic", "SAFEMODE": "false"}) as game:
        settle(game)
        game.keys("M", delay=0.8)
        game.wait_for("ACTIVE MISSIONS")
        assert_page_closed(game)
        game.keys("Escape", delay=0.6)
        game.keys(")", delay=0.8)
        game.wait_for("ACHIEVEMENTS")
        game.keys("Escape", delay=0.6)
        game.wait_for(PLAY_ROW)


def test_world_page_arrows_and_inner_pages(_g):
    with world_game() as game:
        settle(game)
        open_page(game)

        game.keys("Right", delay=0.5)
        game.wait_for("<│2 Factions│>")
        game.wait_for("YOUR FOLLOWERS")
        game.keys("Right", delay=0.5)
        game.wait_for("<│3 Zones│>")
        game.wait_for("Zones (")
        game.keys("Left", delay=0.5)
        game.wait_for("<│2 Factions│>")

        game.keys("Tab", delay=0.5)
        game.wait_for("OTHER FACTIONS")
        game.wait_for("<│2 Factions│>")

        game.keys("Escape", delay=0.6)
        game.wait_gone(tab_strip("2 Factions"))
        assert_page_closed(game)
        game.wait_for(PLAY_ROW)


def text_position(game, text):
    for y, line in enumerate(game.screen().splitlines()):
        x = line.find(text)
        if x >= 0:
            return x, y
    raise AssertionError(f"no {text!r} on screen\n" + game.screen())


def test_world_page_saves_zone_edits_before_leaving(_g):
    with world_game() as game:
        settle(game)
        open_page(game)
        game.keys("3", delay=0.7)
        game.wait_for("<│3 Zones│>")
        game.wait_for("Zones (")

        game.keys("A", delay=0.8)
        game.wait_for("Select zone type:")
        x, y = text_position(game, "Auto Drink")
        game.double_click(x, y)
        game.wait_for("Zone name:")
        game.keys("Enter", delay=0.6)

        game.wait_for("Select first point.")
        assert_page_closed(game)
        game.keys("Enter", delay=0.6)
        game.wait_for("Select second point.")
        assert_page_closed(game)
        game.keys("Enter", delay=0.6)
        game.wait_for("Zones (1)")
        game.wait_for(tab_strip("3 Zones"))

        x, y = text_position(game, "Auto Drink")
        game.click(x, y)
        game.click(x, y)
        game.wait_for("What do you want to change:")
        game.keys("Escape", delay=0.6)
        game.wait_gone("What do you want to change:")

        game.keys("Escape", delay=0.6)
        game.wait_for("Save changes?")
        game.keys("Left", delay=0.3)
        game.keys("Enter", delay=0.8)
        game.wait_gone(tab_strip("3 Zones"))
        assert_page_closed(game)
        game.wait_for(PLAY_ROW)
        saved = list((game.userdir / "save").glob("*/*.zones.json"))
        assert saved, "accepting the prompt must write the player's zone file"

        open_page(game)
        game.keys("3", delay=0.7)
        game.wait_for("<│3 Zones│>")
        game.wait_for("Zones (1)")
        game.keys("Escape", delay=0.6)
        game.wait_gone(tab_strip("3 Zones"))
        assert_page_closed(game)
        game.wait_for(PLAY_ROW)


def test_world_page_embeds_in_the_sidebar(_g):
    with shared_game("bn-e2e-world-sidebar", define=HELPERS, setup=arena, cols=COLS, rows=ROWS,
                     layout="fusion",
                     options={"CONTROL_SCHEME": "modern", "SAFEMODE": "false",
                              "SHOW_WELCOME": "false", "SHOW_TIPS": "false"}) as game:
        game.keys("M", delay=0.8)
        game.wait_for("1 Missions")
        page = game.screen()
        column = "\n".join(line[COLS - SIDEBAR:] for line in page.splitlines())
        assert "2 Factions" in column and "3 Zones" in column, \
            "the tabs sit in the sidebar:\n" + page
        assert "\n".join(line[:COLS - SIDEBAR] for line in page.splitlines()).strip(), \
            "the map stays beside the page:\n" + page

        game.keys("Right", delay=0.6)
        assert "1 Missions" in game.screen(), "the arrow stays on the page:\n" + game.screen()

        game.keys("Escape", delay=0.6)
        assert_page_closed(game)

        game.keys("M", delay=0.8)
        game.wait_for("1 Missions")
        game.keys("1", delay=0.6)
        game.keys("Enter", delay=0.8)
        game.wait_for("ACTIVE MISSIONS")
        game.keys("Escape", delay=0.6)
        game.wait_gone("<│ACTIVE MISSIONS│>")
        assert_page_closed(game)


TESTS = [
    test_world_screens_stay_bindable_without_plain_marker_keys,
    test_world_page_draws_tab_content_inline,
    test_world_page_reaches_the_zone_actions,
    test_classic_direct_keys_still_open_their_screens,
    test_world_page_arrows_and_inner_pages,
    test_world_page_saves_zone_edits_before_leaving,
    test_world_page_embeds_in_the_sidebar,
]

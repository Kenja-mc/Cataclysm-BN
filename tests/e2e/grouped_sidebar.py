"""Right-sidebar HUD groups stay readable without covering the world map."""
import re
from contextlib import contextmanager

from aim_reticle import action_clock
from fixtures import shared_game
from helpers import HELPERS, arena, empty_inventory, give
from hud_boxes import sky_track
from hud_status import healthy, regions, resized_frame
from tmux_game import Game, start_new_game


OPTIONS = {"CONTROL_SCHEME": "modern", "SAFEMODE": "false", "SHOW_WELCOME": "false",
           "SHOW_TIPS": "false", "SIDEBAR_POSITION": "right", "SIDEBAR_SPACERS": "false",
           "HUD_WEATHER_BOX": "top_left", "HUD_COMBAT_BOX": "top_left",
           "HUD_VEHICLE_BOX": "top_left", "HUD_ICONS": "unicode", "ANIMATIONS": "false"}
NEED_LABELS = ("Pain", "Thirst", "Hunger", "Rest", "Body temp")


def grouped_setup(game):
    game.resize(140, 45)
    empty_inventory(game)
    arena(game)
    healthy(game)
    assert game.lua("local a=gapi.get_avatar() a:set_movement_mode(CharacterMoveMode.walk) "
                    "a:get_magic():set_mana(1) out('ok')") == ["ok"]


@contextmanager
def grouped_game():
    with shared_game("bn-e2e-grouped-sidebar", options=OPTIONS, layout="grouped",
                     define=HELPERS, setup=grouped_setup) as game:
        yield game


def assert_hud_on_right(screen, cols=140):
    terrain, sidebar = regions(screen, cols)
    for fact in ("Light:", "Wind:", "Walking", "Needs met", "Character"):
        assert fact not in terrain, "grouped HUD must leave the world map clear:\n" + screen
    assert not re.search(r"\b(?:Weapon|Stance|Mana)\s*\|", terrain), screen
    assert "No style" not in sidebar, "an unset style must not occupy a sidebar row:\n" + screen
    for fact in ("Light:", "Wind:", "Walking"):
        assert sidebar.count(fact) == 1, "a HUD fact must appear exactly once in the sidebar:\n" + screen
    date_rows = [line for line in sidebar.splitlines() if re.search(r"\b(?:Spring|Summer|Autumn|Winter)\s+\d+", line)]
    assert len(date_rows) == 1, "date/time must have one owner:\n" + screen
    sky_track(date_rows[0])
    return sidebar


def test_grouped_sidebar_fresh_default_has_no_map_overlays(_g):
    # No panel_options.json is seeded: this is the actual first-run layout, not an option mock.
    game = Game("bn-e2e-grouped-default", options=OPTIONS, layout=None)
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        grouped_setup(game)
        game.settle_screen()
        screen = game.screen()
        sidebar = assert_hud_on_right(screen)
        for title in ("Weather", "Character", "Needs"):
            assert len(re.findall(r"╭[^\n]*\b" + title + r"\b", sidebar)) == 1, screen
        assert sidebar.count("Needs met") == 1, screen
        for label in NEED_LABELS:
            assert not re.search(r"\b" + label + r"\s*[|:]", sidebar), screen
        assert re.search(r"1/\d+", sidebar), "spent mana must remain visible in Character:\n" + screen
    finally:
        game.close()


def test_grouped_sidebar_resize_keeps_urgent_needs_and_controls(_g):
    with grouped_game() as game:
        assert game.lua("local a=gapi.get_avatar() a:set_pain(60) a:set_thirst(400) "
                        "a:set_fatigue(400) a:set_stored_kcal(1000) "
                        "a:set_temp_celsius(Temperature.from_celsius(44)) out('ok')") == ["ok"]
        before = action_clock(game)
        for cols, rows in ((140, 45), (100, 41), (100, 40), (100, 39), (100, 30),
                           (80, 25), (140, 45)):
            game.resize(cols, rows)
            # Narrow groups fold the needs summary, so a label may break at its space.
            screen = resized_frame(game, cols, rows, lambda s: all(
                word in regions(s, cols)[1] for word in ("Thirst", "Hunger", "all keys")) and
                re.search(r"Body\s+temp", regions(s, cols)[1]))
            sidebar = assert_hud_on_right(screen, cols)
            assert "Needs met" not in sidebar, screen
            for label in NEED_LABELS:
                pattern = r"\b" + r"\s+".join(label.split()) + r"\b"
                assert len(re.findall(pattern, sidebar)) == 1, \
                    "every urgent need must survive resizing without duplication:\n" + screen
            for fact in ("HEAD", "TORSO", "Move", "Safe", "all keys"):
                assert fact in sidebar, "essential status/control is missing after resize:\n" + screen
            if rows >= 40:
                assert "Character" in sidebar and "Needs" in sidebar, screen
        assert action_clock(game) == before, "responsive HUD changes must not advance game time"


def test_grouped_sidebar_instruments_do_not_duplicate_clock(_g):
    with grouped_game() as game:
        before = action_clock(game)
        without = assert_hud_on_right(game.screen())
        assert not re.search(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", without), \
            "no watch must mean approximate time:\n" + without
        give(game, "pocketwatch")
        give(game, "thermometer")
        game.settle_screen()
        measured = assert_hud_on_right(game.screen())
        assert len(re.findall(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", measured)) == 1, measured
        assert len(re.findall(r"[-+]?\d+(?:\.\d+)?\s*°\s*[CFK]", measured)) == 1, measured
        assert action_clock(game) == before, "instrument knowledge must not spend time"


TESTS = [test_grouped_sidebar_fresh_default_has_no_map_overlays,
         test_grouped_sidebar_resize_keeps_urgent_needs_and_controls,
         test_grouped_sidebar_instruments_do_not_duplicate_clock]

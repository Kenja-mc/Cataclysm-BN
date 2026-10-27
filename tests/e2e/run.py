#!/usr/bin/env python3
"""End-to-end checks for the overhaul, played through the real curses binary in tmux.

Each feature module exposes its own `TESTS`. A test that takes `g` runs on the runner's
main game; a test that needs other options borrows the game for its option profile from
fixtures.py, which keeps one game per profile for the whole process.

  python3 tests/e2e/run.py                    whole suite, parallel when the machine allows
  python3 tests/e2e/run.py <substring>...      only tests whose name contains one of these
  python3 tests/e2e/run.py --list              every registered test once, with its module
  python3 tests/e2e/run.py --tier=smoke        one representative test per green module
  python3 tests/e2e/run.py --tier=full         every test (the default)
  python3 tests/e2e/run.py --parallel=N        N processes, each with its own games
  python3 tests/e2e/run.py --serial            one process (same as --parallel=1)
  python3 tests/e2e/run.py --shard=I/N         CI: shard I of N, balanced by durations.json
  python3 tests/e2e/run.py --durations=PATH    record per-test seconds for the shard split
  python3 tests/e2e/run.py --serial --keep     leave the main game running for inspection
"""
import json
import os
import sys
import tempfile
import time
import traceback
from contextlib import nullcontext
from pathlib import Path
from subprocess import CalledProcessError

from fixtures import shared_game
from helpers import HELPERS, settle
from tmux_game import Game, start_new_game

from onboarding import TESTS as ONBOARDING_TESTS
from movement import TESTS as MOVEMENT_TESTS
from menus import TESTS as MENUS_TESTS
from world_hub import TESTS as WORLD_HUB_TESTS
from action_search import TESTS as ACTION_SEARCH_TESTS
from items import TESTS as ITEMS_TESTS
from storage import TESTS as STORAGE_TESTS
from crafting import TESTS as CRAFTING_TESTS
from hud_boxes import TESTS as HUD_BOXES_TESTS
from map_view import TESTS as MAP_VIEW_TESTS
from combat import TESTS as COMBAT_TESTS
from sound_feedback import TESTS as SOUND_FEEDBACK_TESTS
from monster_ambience import TESTS as MONSTER_AMBIENCE_TESTS
from activity_line import TESTS as ACTIVITY_LINE_TESTS
from sound_menu import TESTS as SOUND_MENU_TESTS
from safemode import TESTS as SAFEMODE_TESTS
from char_creation import TESTS as CHAR_CREATION_TESTS
from fluid_grid import TESTS as FLUID_GRID_TESTS
from river_barges import TESTS as RIVER_BARGES_TESTS
from vehicle_box import TESTS as VEHICLE_BOX_TESTS
from remote_vehicle import TESTS as REMOTE_VEHICLE_TESTS
from cursor_panning import TESTS as CURSOR_PANNING_TESTS
from npc_palette import TESTS as NPC_PALETTE_TESTS
from hud_sidebar import TESTS as HUD_SIDEBAR_TESTS
from construction_tab import TESTS as CONSTRUCTION_TAB_TESTS
from dispose_menu import TESTS as DISPOSE_MENU_TESTS
from fire_feedback import TESTS as FIRE_FEEDBACK_TESTS
from keyhints_small import TESTS as KEYHINTS_SMALL_TESTS
from context_keyhints import TESTS as CONTEXT_KEYHINTS_TESTS
from safe_mode_sleep import TESTS as SAFE_MODE_SLEEP_TESTS
from vehicle_memory import TESTS as VEHICLE_MEMORY_TESTS
from aim_reticle import TESTS as AIM_RETICLE_TESTS
from safe_click import TESTS as SAFE_CLICK_TESTS
from map_mouse import TESTS as MAP_MOUSE_TESTS
from inventory_mouse import TESTS as INVENTORY_MOUSE_TESTS
from pickup_flow import TESTS as PICKUP_FLOW_TESTS
from modern_map_controls import TESTS as MODERN_MAP_CONTROLS_TESTS
from options_menu import TESTS as OPTIONS_MENU_TESTS
from inventory_hub import TESTS as INVENTORY_HUB_TESTS
from contextual_hub import TESTS as CONTEXTUAL_HUB_TESTS
from grouped_controls import TESTS as GROUPED_CONTROLS_TESTS
from hud_status import TESTS as HUD_STATUS_TESTS
from world_presets import TESTS as WORLD_PRESETS_TESTS
from interaction_routes import TESTS as INTERACTION_ROUTES_TESTS
from tutorial_routes import TESTS as TUTORIAL_ROUTES_TESTS
from grouped_sidebar import TESTS as GROUPED_SIDEBAR_TESTS
from unbound_mouse import TESTS as UNBOUND_MOUSE_TESTS
from menu_scrollbars import TESTS as MENU_SCROLLBARS_TESTS
from overmap_controls import TESTS as OVERMAP_CONTROLS_TESTS
from target_lock import TESTS as TARGET_LOCK_TESTS
from numeric_invkeys import TESTS as NUMERIC_INVKEYS_TESTS
from wear_refresh import TESTS as WEAR_REFRESH_TESTS
from creation_crafting_mouse import TESTS as CREATION_CRAFTING_MOUSE_TESTS
from keybinding_search import TESTS as KEYBINDING_SEARCH_TESTS
from pulp_key import TESTS as PULP_KEY_TESTS
from known_locks import TESTS as KNOWN_LOCKS_TESTS
from vehicle_mouse import TESTS as VEHICLE_MOUSE_TESTS
from advanced_armor_mouse import TESTS as ADVANCED_ARMOR_MOUSE_TESTS
from help_score_mouse import TESTS as HELP_SCORE_MOUSE_TESTS
from menu_space import TESTS as MENU_SPACE_TESTS
from status_mouse import TESTS as STATUS_MOUSE_TESTS
from utility_mouse import TESTS as UTILITY_MOUSE_TESTS
from info_mouse import TESTS as INFO_MOUSE_TESTS
from trade_mouse import TESTS as TRADE_MOUSE_TESTS

from title_wordmark import TESTS as TITLE_WORDMARK_TESTS
# The modules, in run order. A module's tests that take `g` run on the main game, so a
# test that needs the state another left behind belongs after it in this order.
MODULES = [
    ("title_wordmark", TITLE_WORDMARK_TESTS),
    ("onboarding", ONBOARDING_TESTS),
    ("movement", MOVEMENT_TESTS),
    ("menus", MENUS_TESTS),
    ("world_hub", WORLD_HUB_TESTS),
    ("action_search", ACTION_SEARCH_TESTS),
    ("items", ITEMS_TESTS),
    ("storage", STORAGE_TESTS),
    ("crafting", CRAFTING_TESTS),
    ("hud_boxes", HUD_BOXES_TESTS),
    ("map_view", MAP_VIEW_TESTS),
    ("combat", COMBAT_TESTS),
    ("sound_feedback", SOUND_FEEDBACK_TESTS),
    ("monster_ambience", MONSTER_AMBIENCE_TESTS),
    ("activity_line", ACTIVITY_LINE_TESTS),
    ("sound_menu", SOUND_MENU_TESTS),
    ("safemode", SAFEMODE_TESTS),
    ("char_creation", CHAR_CREATION_TESTS),
    ("fluid_grid", FLUID_GRID_TESTS),
    ("river_barges", RIVER_BARGES_TESTS),
    ("vehicle_box", VEHICLE_BOX_TESTS),
    ("remote_vehicle", REMOTE_VEHICLE_TESTS),
    ("cursor_panning", CURSOR_PANNING_TESTS),
    ("npc_palette", NPC_PALETTE_TESTS),
    ("hud_sidebar", HUD_SIDEBAR_TESTS),
    ("construction_tab", CONSTRUCTION_TAB_TESTS),
    ("dispose_menu", DISPOSE_MENU_TESTS),
    ("fire_feedback", FIRE_FEEDBACK_TESTS),
    ("keyhints_small", KEYHINTS_SMALL_TESTS),
    ("context_keyhints", CONTEXT_KEYHINTS_TESTS),
    ("safe_mode_sleep", SAFE_MODE_SLEEP_TESTS),
    ("vehicle_memory", VEHICLE_MEMORY_TESTS),
    ("aim_reticle", AIM_RETICLE_TESTS),
    ("safe_click", SAFE_CLICK_TESTS),
    ("map_mouse", MAP_MOUSE_TESTS),
    ("inventory_mouse", INVENTORY_MOUSE_TESTS),
    ("pickup_flow", PICKUP_FLOW_TESTS),
    ("modern_map_controls", MODERN_MAP_CONTROLS_TESTS),
    ("options_menu", OPTIONS_MENU_TESTS),
    ("inventory_hub", INVENTORY_HUB_TESTS),
    ("contextual_hub", CONTEXTUAL_HUB_TESTS),
    ("grouped_controls", GROUPED_CONTROLS_TESTS),
    ("hud_status", HUD_STATUS_TESTS),
    ("interaction_routes", INTERACTION_ROUTES_TESTS),
    ("tutorial_routes", TUTORIAL_ROUTES_TESTS),
    ("grouped_sidebar", GROUPED_SIDEBAR_TESTS),
    ("unbound_mouse", UNBOUND_MOUSE_TESTS),
    ("menu_scrollbars", MENU_SCROLLBARS_TESTS),
    ("overmap_controls", OVERMAP_CONTROLS_TESTS),
    ("target_lock", TARGET_LOCK_TESTS),
    ("numeric_invkeys", NUMERIC_INVKEYS_TESTS),
    ("wear_refresh", WEAR_REFRESH_TESTS),
    ("creation_crafting_mouse", CREATION_CRAFTING_MOUSE_TESTS),
    ("keybinding_search", KEYBINDING_SEARCH_TESTS),
    ("pulp_key", PULP_KEY_TESTS),
    ("known_locks", KNOWN_LOCKS_TESTS),
    ("vehicle_mouse", VEHICLE_MOUSE_TESTS),
    ("advanced_armor_mouse", ADVANCED_ARMOR_MOUSE_TESTS),
    ("help_score_mouse", HELP_SCORE_MOUSE_TESTS),
    ("menu_space", MENU_SPACE_TESTS),
    ("status_mouse", STATUS_MOUSE_TESTS),
    ("utility_mouse", UTILITY_MOUSE_TESTS),
    ("info_mouse", INFO_MOUSE_TESTS),
    ("trade_mouse", TRADE_MOUSE_TESTS),
    # Applies and resets world options on the main world, so it runs last.
    ("world_presets", WORLD_PRESETS_TESTS),
]

MODULE_OF = {test: name for name, tests in MODULES for test in tests}
TESTS = [test for _, tests in MODULES for test in tests]

# One representative test per module, chosen to be fast and to touch the module's main path.
# `--tier=smoke` runs this list in parallel: it is the quick "did anything break" gate.
SMOKE = [
    # One representative test per module, the cheapest one that still exercises its main
    # path. A module whose tests are not green yet stays out of the gate.
    "test_death_mode_choice",
    "test_title_wordmark_visible_on_80x25",
    "test_wait_keeps_position",
    "test_rounded_frames",
    "test_folded_families",
    "test_quick_stack_not_through_windows",
    "test_crafting_opens_on_content",
    "test_readable_map_glyphs",
    "test_enemy_edge_arrows_off",
    "test_magnet_pull_through_monster",
    "test_sound_marker_fading",
    "test_sound_menu_curses_unavailable",
    "test_idle_sound_needs_the_data_field_and_rerolls_its_cooldown",
    "test_activity_line_names_progress_and_time_left",
    "test_smart_safe_mode_horde",
    "test_char_creation_overview_fits_small_terminal",
    "test_partial_grid_transfer_keeps_the_rest",
    # river_barges is registered but stays out of the smoke gate until it is green;
    # add its test here once its owner reports it.
    "test_vehicle_box_aircraft",
    "test_remote_vehicle_controls_menu",
    "test_cursor_panning_off",
    "test_follower_palette_option_off_keeps_the_old_menu",
    "test_modern_reaches_sidebar_options_from_the_menu",
    "test_construction_opens_on_content",
    "test_modern_dispose_empty_filter_explains_and_recovers",
    "test_fire_feedback_no_ranged_weapon",
    "test_controls_strip_shows_on_80x25",
    "test_classic_wait_and_safe_mode_keep_upstream_interface",
    "test_memory_behind_moved_vehicle",
    "test_arrow_keys_aim_and_attack",
    "test_safe_click_option_off",
    "test_hover_inspects_without_acting",
    "test_right_click_opens_item_actions",
    "test_g_again_picks_up_the_highlighted_item",
    "test_options_reset_to_default",
    "test_classic_inventory_has_no_craft_hub",
    "test_contextual_no_selection_lists_nearby_actions",
    "test_grouped_distant_melee_selection_never_redirects_or_walks",
    "test_status_short_narrow_fallback_retains_needs",
    "test_contextual_left_click_opens_and_closes_without_walking",
    "test_classic_tutorial_preserves_classic_controls",
    "test_grouped_sidebar_fresh_default_has_no_map_overlays",
    "test_unbound_mouse_wheel_is_silent",
    "test_uilist_scrollbar_jumps_and_arrows",
    "test_m_toggles_overmap_without_travel",
    "test_f_without_selection_attacks_an_adjacent_enemy",
    "test_modern_reassign_accepts_digit_and_digit_selects_item",
    "test_wear_moves_shirt_into_worn_and_keeps_menu_open",
    "test_modern_crafting_scrollbar_moves_selection_without_crafting",
    "test_letters_search_keybindings_after_scrolling",
    "test_modern_attack_pulps_the_chosen_corpse",
    "test_world_defaults_unchanged_without_preset",
]
SMOKE_TESTS = [test for test in TESTS if test.__name__ in SMOKE]


def list_tests():
    """Every registered test once, with its module, so a duplicate shows up here first."""
    seen = {}
    for test in TESTS:
        assert test.__name__ not in seen, f"{test.__name__} is registered twice"
        seen[test.__name__] = MODULE_OF[test]
    missing = sorted(name for name in SMOKE if name not in seen)
    assert not missing, f"the smoke tier names unregistered tests: {missing}"
    durations = recorded_durations()
    for test in TESTS:
        seconds = durations.get(test.__name__)
        print(f"{MODULE_OF[test]:<18} {test.__name__:<58} "
              f"{'-' if seconds is None else f'{seconds:.1f}s'}")
    print(f"{len(TESTS)} tests, {len({MODULE_OF[t] for t in TESTS})} modules, "
          f"{len(SMOKE_TESTS)} in the smoke tier")


DURATIONS = Path(__file__).with_name("durations.json")


def recorded_durations():
    """Per-test seconds from the last run, used to split the shards by cost."""
    try:
        return json.loads(DURATIONS.read_text())
    except (OSError, ValueError):
        return {}


def shard_of(tests, index, count):
    """Assigns a whole test to one shard, longest first into the lightest bin.

    Positional slicing cost a third of the CI wall time: the three mouse tests sat in one
    shard and made it 47% longer than its neighbours. A test stays whole, so tests keep
    their relative order inside a shard and shared state behaves as it did.
    """
    if count == 1:
        return list(tests)
    durations = recorded_durations()
    default = sorted(durations.values())[len(durations) // 2] if durations else 30.0
    bins = [[] for _ in range(count)]
    loads = [0.0] * count
    for test in sorted(tests, key=lambda t: -durations.get(t.__name__, default)):
        lightest = min(range(count), key=loads.__getitem__)
        bins[lightest].append(test)
        loads[lightest] += durations.get(test.__name__, default)
    # Keep the suite's own order inside a shard: shared state depends on it.
    order = {test: n for n, test in enumerate(tests)}
    return sorted(bins[index], key=order.__getitem__)


def run_parallel(count, forward):
    """Runs `count` shards at once, each its own game, and prefixes their output by shard."""
    import subprocess
    import threading
    logs = Path(tempfile.mkdtemp(prefix="bn-e2e-parallel-"))
    processes = {}
    threads = []
    for index in range(count):
        durations = logs / f"shard-{index}.json"
        process = subprocess.Popen(
            [sys.executable, __file__, f"--shard={index}/{count}", f"--durations={durations}", *forward],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        processes[index] = (process, durations)

        def pump(shard, stream=process.stdout):
            for line in stream:
                print(f"[{shard}] {line}", end="")
        thread = threading.Thread(target=pump, args=(index,), daemon=True)
        threads.append(thread)
        thread.start()
    failed = 0
    merged = {}
    for index, (process, durations) in processes.items():
        if process.wait():
            failed += 1
        if durations.exists():
            merged.update(json.loads(durations.read_text()))
    for thread in threads:
        thread.join()
    wanted = next((a.split("=", 1)[1] for a in forward if a.startswith("--durations=")), "")
    if wanted:
        Path(wanted).write_text(json.dumps(merged, indent=1, sort_keys=True) + "\n")
    print(f"{count} shards finished, {failed} failed")
    return 1 if failed else 0


def default_setup(game):
    """The main game's start state, also run when another test borrows its profile."""
    settle(game)
    # Lua-created inventory must not depend on the random starting outfit's pockets.
    assert game.lua("gapi.get_avatar():set_mutation(MutationBranchId.new('DEBUG_STORAGE')) out('ok')") == ["ok"]


def default_parallel():
    """Four games at once keeps the input queues short; a small machine runs fewer."""
    return min(4, max(1, (os.cpu_count() or 1) // 4))


def smoke_parallel():
    """The smoke tier is short and starts fewer games per shard, so it runs wider."""
    return min(6, max(2, (os.cpu_count() or 1) // 2))


def main():
    args = sys.argv[1:]
    keep = "--keep" in args
    if "--help" in args or "-h" in args:
        print(__doc__)
        return 0
    if any(a in ("--parallel", "--shard", "--durations", "--tier") for a in args):
        sys.exit("use --parallel=N, --shard=I/N, --durations=PATH and --tier=smoke|full")
    known = ("--keep", "--list", "--serial", "--tier=", "--parallel=", "--shard=", "--durations=")
    unknown = [a for a in args if a.startswith("-") and not a.startswith(known)]
    if unknown:
        sys.exit(f"unknown option {unknown[0]}; see --help")
    if "--list" in args:
        list_tests()
        return 0
    tier = next((a.split("=", 1)[1] for a in args if a.startswith("--tier=")), "full")
    if tier not in ("smoke", "full"):
        sys.exit("--tier must be smoke or full")
    wanted = [a for a in args if not a.startswith("--")]
    if wanted and not any(any(w in t.__name__ for w in wanted) for t in TESTS):
        sys.exit("no tests match the requested names")
    serial = "--serial" in args
    forward = [a for a in args if a not in ("--serial",)]
    # --parallel=<n> runs n shards at once on one machine; the suite is serial otherwise.
    parallel = next((a.split("=", 1)[1] for a in args if a.startswith("--parallel=")), None)
    if any(a.startswith("--shard=") for a in args) and (parallel is not None or serial):
        sys.exit("--shard cannot be combined with --parallel or --serial")
    if parallel is None and not serial and not any(a.startswith("--shard=") for a in args) and not keep:
        parallel = str(smoke_parallel() if tier == "smoke" else default_parallel())
    if parallel is not None:
        try:
            count = int(parallel)
        except ValueError:
            sys.exit("--parallel must be a positive integer")
        if count < 1:
            sys.exit("--parallel must be a positive integer")
        if count > 1:
            forward = [a for a in forward if not a.startswith("--parallel=")]
            if keep:
                sys.exit("--keep needs --serial, because the parallel parent exits with its shards")
            return run_parallel(count, forward)
        forward = [a for a in forward if not a.startswith("--parallel=")]
    # --shard=<index>/<count> splits the suite for parallel jobs, balanced by the recorded
    # per-test durations (tests/e2e/durations.json) so no shard sets the wall time alone.
    shard = next((a for a in forward if a.startswith("--shard=")), "")
    if shard:
        index, count = (int(v) for v in shard.split("=", 1)[1].split("/"))
        if not 0 <= index < count:
            sys.exit(f"{shard}: the index must be below the shard count")
    else:
        index, count = 0, 1
    # --durations=<path> records this run's per-test seconds, for the next shard split.
    record = next((a.split("=", 1)[1] for a in forward if a.startswith("--durations=")), "")
    pool = TESTS if tier == "full" else SMOKE_TESTS
    chosen = shard_of(pool, index, count)
    if wanted:
        chosen = [t for t in chosen if any(w in t.__name__ for w in wanted)]
    if not chosen:
        if record:
            Path(record).write_text("{}\n")
        print("0/0 passed")
        return 0
    # A shard's private tmux server cannot starve another shard of input.
    os.environ.pop("TMUX", None)
    socket_dir = tempfile.mkdtemp(prefix="bn-e2e-tmux-")
    os.environ["TMUX_TMPDIR"] = socket_dir
    if keep:
        os.environ["BN_E2E_KEEP"] = "1"
        g = Game(options={"SAFEMODE": "false", "SOUND_MARKER_TURNS": "3"})
        start_new_game(g)
        settle(g)
        g.define_lua(HELPERS)
        assert g.lua("gapi.get_avatar():set_mutation(MutationBranchId.new('DEBUG_STORAGE')) out('ok')") == ["ok"]
    else:
        return run_tests(chosen, record=record)
    try:
        failures = run_tests(chosen, g, record)
    finally:
        print(f"Kept game: env -u TMUX TMUX_TMPDIR={socket_dir} tmux -L default attach-session -t {g.name}")
        print(f"User directory: {g.userdir}")
    return failures


def run_tests(chosen, g=None, record=""):
    failures = 0
    timings = {}
    for test in chosen:
        started = time.time()
        try:
            # Borrow for one test, not the whole suite: a retired profile is replaced on
            # the next iteration, while successful tests still share the cached game.
            context = nullcontext(g) if g is not None else shared_game(
                "bn-e2e", options={"SAFEMODE": "false", "SOUND_MARKER_TURNS": "3"},
                define=HELPERS, setup=default_setup)
            with context as game:
                try:
                    game.dismiss_error_popup()
                    test(game)
                except Exception:
                    # Capture the failure before the fixture's final borrower closes it.
                    try:
                        print(game.screen())
                    except CalledProcessError as error:
                        print(f"tmux game unavailable: {error.stderr or error}")
                    raise
            print(f"PASS {test.__name__} ({time.time() - started:.1f}s)")
            timings[test.__name__] = round(time.time() - started, 1)
        except Exception:
            failures += 1
            print(f"FAIL {test.__name__}")
            traceback.print_exc()
            if g is not None:
                # --keep deliberately preserves the same game, including after a failure.
                try:
                    g.keys("Escape", delay=0.5)
                    g.dismiss_error_popup()
                except CalledProcessError as error:
                    print(f"kept tmux game unavailable: {error.stderr or error}")
    if record:
        Path(record).write_text(json.dumps(timings, indent=1, sort_keys=True) + "\n")
        print(f"recorded {len(timings)} test durations to {record}")
    ran = len(chosen)
    print(f"{ran - failures}/{ran} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

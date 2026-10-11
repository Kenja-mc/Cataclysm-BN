#!/usr/bin/env python3
"""Playtest harness — prepares scenarios in a real game and hands off to human inspection.

Usage:
    python3 tests/e2e/playtest.py --list
    python3 tests/e2e/playtest.py <scenario> [--tiles] [--scheme modern|classic] [--no-attach]
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Ensure the e2e directory is on sys.path so we can import tmux_game / helpers
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tmux_game import Game, start_new_game
from helpers import HELPERS, arena, spawn, give, settle

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------
# Each scenario is a dict with:
#   id          — CLI identifier
#   description — human-readable one-liner for --list
#   setup       — single-line Lua code string run after start_new_game
#   checklist   — list of strings printed for the human to verify
#   options     — optional dict for Game(options=...)

SCENARIOS = [
    # ── Features on main ────────────────────────────────────────────────────
    {
        "id": "quick_stack",
        "description": "Quick-stack (Q) items into nearby storage furniture",
        "setup": "arena() spawn(2,0,'usb_drive',1,'f_rack') give('usb_drive',3) give('plastic_six_dice',1)",
        "checklist": [
            "Press Q — items on the ground should fly into the rack.",
            "Check sidebar: 'Stashed N items into 1 spot'.",
            "Dice stay behind (nothing nearby holds them).",
        ],
    },
    {
        "id": "sort_pile",
        "description": "Sort pile (Z) groups mixed items into storage by category",
        "setup": "arena() spawn(3,0,'usb_drive',1,'f_rack') spawn(-3,0,'flyer',1,'f_rack') spawn(0,0,'usb_drive',2) spawn(0,0,'character_sheet',1) spawn(0,0,'plastic_six_dice',1)",
        "checklist": [
            "Press Z — items sort into nearby racks by type.",
            "USB drives join the rack at (3,0); character sheets and books go to (-3,0).",
            "Dice stay in the pile (no matching storage).",
        ],
    },
    {
        "id": "combine_tools",
        "description": "Combine (C) partly used matchbooks into one stack",
        "setup": "arena() gapi.get_avatar():create_item(ItypeId.new('matches'),1):set_charges(5) gapi.get_avatar():create_item(ItypeId.new('matches'),1):set_charges(7)",
        "checklist": [
            "Open inventory (i), search 'matchbook', press C.",
            "Two matchbooks (5+7 charges) should merge into one with 12 charges.",
            "Sidebar: 'You combine 2 matchbooks into one.'",
        ],
    },
    {
        "id": "item_folding",
        "description": "Black powder ammo stacks with factory ammo; jewelry variants",
        "setup": "arena() give('bp_9mm',10) give('9mm',20) give('jewelry_ring',1) local r=gapi.get_avatar():get_item_by_type(ItypeId.new('jewelry_ring')) if r then r:set_var_str('variant','ruby_gold_ring') end",
        "checklist": [
            "Open inventory (i) — bp_9mm and 9mm should share one stack line.",
            "The ring shows as 'ruby and gold ring' (variant system).",
            "Check that old item IDs are gone (no separate bp_9mm item type).",
        ],
    },
    {
        "id": "hud_boxes",
        "description": "HUD weather and weapon boxes in the top-left corner",
        "setup": "arena()",
        "checklist": [
            "Look at top-left corner of the map for weather and weapon boxes.",
            "Weapon box shows the currently wielded weapon icon.",
            "Weather box shows current weather icon.",
        ],
    },
    {
        "id": "aiming",
        "description": "Aim mode (f) defaults with a gun and a zombie in range",
        "setup": "arena() give('m9',1) give('9mm',30) gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(4,0))",
        "checklist": [
            "Press f to enter aim mode.",
            "Check that the aim reticle appears and defaults to the zombie.",
            "Fire and confirm the zombie takes damage.",
        ],
    },
    {
        "id": "click_interact",
        "description": "Hover and click to attack; right-click for action menu",
        "setup": "arena() gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(2,0)) settle()",
        "checklist": [
            "Hover over the zombie — sidebar should say 'click: attack'.",
            "Left-click the zombie — it should take damage.",
            "Right-click the zombie — an action menu appears with options.",
        ],
    },
    {
        "id": "gun_loudness",
        "description": "Gun item info shows loudness rating",
        "setup": "arena() give('m9',1) give('rifle_556',1) give('shotgun',1)",
        "checklist": [
            "Open inventory (i), search for each gun, press Enter for item info.",
            "Each gun's info page shows a 'Loudness: N (silent|quiet|loud|very loud|deafening)' line.",
            "Louder guns should show higher numbers.",
        ],
    },
    # ── Features landing soon ───────────────────────────────────────────────
    {
        "id": "sound_markers",
        "description": "Sound markers appear on map for noises behind walls",
        "setup": "arena() for dy=-3,3 do M:set_ter_at(here(3,dy),TerId.new('t_brick_wall'):int_id()) end gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(5,0)) gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(6,2))",
        "checklist": [
            "Look at the map — sound markers should appear where zombies are.",
            "Markers show through the wall at (3,0) line.",
            "Different noise levels may show different marker styles.",
        ],
    },
    {
        "id": "smart_targeting",
        "description": "Targeting skips allied creatures (dogs) between player and enemies",
        "setup": "arena() gapi.place_monster_at(MonsterTypeId.new('mon_dog'),here(2,0)) gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(4,0)) gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(5,0)) give('m9',1) give('9mm',30)",
        "checklist": [
            "Press f to enter aim mode.",
            "The dog ally at (2,0) should be skipped — aim defaults to the first zombie.",
            "Press Tab to cycle targets — dog should not appear in the target list.",
        ],
    },
    {
        "id": "smart_safe_mode",
        "description": "Safe mode handles unreachable vs reachable threats differently",
        "setup": "arena() for dy=-3,3 do M:set_ter_at(here(3,dy),TerId.new('t_brick_wall'):int_id()) end gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(5,0)) gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(-2,0))",
        "checklist": [
            "With safe mode on, the reachable zombie should trigger a warning.",
            "The zombie behind the wall should not trigger safe mode.",
            "Toggle safe mode and verify behavior changes.",
        ],
    },
    {
        "id": "stances",
        "description": "Stance options (stand/crouch/kneel) available in combat",
        "setup": "arena() gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(3,0))",
        "checklist": [
            "Look for stance indicator in the sidebar or HUD.",
            "Try stance keys (typically 's' or via action menu) to crouch/kneel.",
            "Verify stance affects visibility/accuracy as described.",
        ],
    },
    {
        "id": "contextual_interact",
        "description": "Space bar contextually interacts with adjacent objects (doors)",
        "setup": "arena() M:set_ter_at(here(1,0),TerId.new('t_door_c'):int_id())",
        "checklist": [
            "Stand next to the closed door.",
            "Press Space — the door should open (contextual interaction).",
            "Press Space again — the door should close.",
            "No menu should appear for a simple door toggle.",
        ],
    },
    {
        "id": "crafting_chains",
        "description": "Crafting menu suggests chains for recipes with missing components",
        "setup": "arena() give('glass_shard',3)",
        "checklist": [
            "Open crafting menu (k).",
            "Search for 'glass shard trap'.",
            "The recipe should show a chain suggestion for the missing component.",
            "Follow the chain to see the full crafting tree.",
        ],
    },
    {
        "id": "status_effects",
        "description": "Status effects display for bleeding/poisoned creatures",
        "setup": "arena() gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(2,0)) gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(3,1)) gapi.get_avatar():add_effect(efftype_id.new('bleed'),10)",
        "checklist": [
            "Check the player HUD/sidebar — a bleeding indicator should appear.",
            "Hover over zombies to see their status effects.",
            "Open the body panel (H) to see detailed status effects.",
        ],
    },
]


def find_tiles_binary():
    """Return the tiles binary path, or None if not found."""
    candidates = [
        Path("/home/user/Projects/Cataclysm-BN/out/build/linux-full/src/cataclysm-bn-tiles"),
        Path(__file__).resolve().parents[2] / "cataclysm-bn-tiles",
        Path(__file__).resolve().parents[2] / "build" / "src" / "cataclysm-bn-tiles",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def find_world_name(userdir):
    """Find the world name from the save directory."""
    save_dir = Path(userdir) / "save"
    if not save_dir.exists():
        return None
    worlds = [d for d in save_dir.iterdir() if d.is_dir()]
    return worlds[0].name if worlds else None


def save_and_quit(game):
    """Send save keys and wait for the game to return to menu."""
    game.keys("Escape", delay=1)
    game.keys("S", delay=1.5)
    game.keys("y", delay=0.5)
    game.keys("Enter", delay=1.5)
    time.sleep(2)


def run_scenario(scenario_id, tiles=False, scheme=None, no_attach=False):
    """Run a single scenario and hand off to the human."""
    scenario = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    if scenario is None:
        print(f"Unknown scenario: {scenario_id}")
        print(f"Available: {', '.join(s['id'] for s in SCENARIOS)}")
        return 1

    userdir = Path(f"/tmp/bn-playtest/{scenario_id}")
    session_name = f"bn-playtest-{scenario_id}"

    # Clean up any previous session
    subprocess.run(["tmux", "kill-session", "-t", session_name],
                   stderr=subprocess.DEVNULL)
    if userdir.exists():
        shutil.rmtree(userdir)
    userdir.mkdir(parents=True)

    options = {"SAFEMODE": "false"}
    if scheme:
        options["CONTROL_SCHEME"] = scheme
    if scenario.get("options"):
        options.update(scenario["options"])

    print(f"=== Scenario: {scenario['id']} — {scenario['description']} ===")
    print(f"Userdir: {userdir}")
    print(f"Options: {options}")
    print()

    g = Game(name=session_name, options=options, userdir=str(userdir))

    try:
        start_new_game(g)
        settle(g)
        g.define_lua(HELPERS)

        # Run the scenario setup Lua (single line)
        setup_code = scenario["setup"]
        if setup_code.strip():
            result = g.lua(setup_code)
            print(f"Setup result: {result}")
            time.sleep(1)

        settle(g)

        # Print checklist
        print("─" * 60)
        print("CHECKLIST:")
        for item in scenario["checklist"]:
            print(f"  □ {item}")
        print("─" * 60)
        print()

        if tiles:
            # Save and quit curses, then launch tiles
            print("Saving and quitting curses session...")
            save_and_quit(g)
            subprocess.run(["tmux", "kill-session", "-t", g.name], stderr=subprocess.DEVNULL)

            world_name = find_world_name(userdir)
            if not world_name:
                print("ERROR: Could not find world name in save directory")
                return 1

            tiles_bin = find_tiles_binary()
            if not tiles_bin:
                print("ERROR: cataclysm-bn-tiles binary not found")
                return 1

            print(f"Launching tiles binary: {tiles_bin}")
            print(f"  --userdir {userdir} --world {world_name}")

            env = os.environ.copy()
            env["SDL_VIDEODRIVER"] = "offscreen"

            proc = subprocess.Popen(
                [str(tiles_bin), "--basepath",
                 str(Path(__file__).resolve().parents[2]) + "/",
                 "--userdir", str(userdir) + "/", "--world", world_name],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Let it run for a few seconds to load
            time.sleep(8)

            # Check for save loading evidence in debug.log
            debug_log = userdir / "config" / "debug.log"
            if debug_log.exists():
                log_text = debug_log.read_text(errors="replace")
                if "Loading saved game" in log_text or "load" in log_text.lower():
                    print("✓ Tiles binary loaded the save (debug.log evidence)")
                else:
                    print("⚠ No explicit save-load evidence in debug.log")
                    print(f"  Log tail: {log_text[-200:]}")
            else:
                print("⚠ No debug.log found in userdir/config/")

            proc.terminate()
            print("Tiles process terminated.")
            return 0

        elif no_attach:
            # Capture screen and kill session
            screen = g.screen()
            print("SCREEN CAPTURE:")
            print("=" * 60)
            print(screen)
            print("=" * 60)
            g.close()
            print("Session killed.")
            return 0

        else:
            # Default: attach to the session
            if sys.stdin.isatty():
                print(f"Attaching to tmux session: {session_name}")
                print("Detach with Ctrl+B then D")
                os.execvp("tmux", ["tmux", "attach", "-t", session_name])
            else:
                print(f"Not a TTY. Run this to attach:")
                print(f"  tmux attach -t {session_name}")
                print()
                print("Screen capture:")
                print(g.screen())
                return 0

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        g.close()
        return 1


def main():
    parser = argparse.ArgumentParser(description="Cataclysm-BN playtest harness")
    parser.add_argument("scenario", nargs="?", help="Scenario ID to run")
    parser.add_argument("--list", action="store_true", help="List all scenarios")
    parser.add_argument("--tiles", action="store_true",
                        help="Save and quit curses, launch tiles binary")
    parser.add_argument("--scheme", choices=["modern", "classic"],
                        help="Control scheme to use")
    parser.add_argument("--no-attach", action="store_true",
                        help="Capture screen and kill session instead of attaching")

    args = parser.parse_args()

    if args.list:
        print("Available scenarios:")
        print()
        for s in SCENARIOS:
            print(f"  {s['id']:<25} — {s['description']}")
        print()
        print(f"Total: {len(SCENARIOS)} scenarios")
        return 0

    if not args.scenario:
        parser.print_help()
        print()
        print("Use --list to see all scenarios.")
        return 1

    return run_scenario(
        args.scenario,
        tiles=args.tiles,
        scheme=args.scheme,
        no_attach=args.no_attach,
    )


if __name__ == "__main__":
    sys.exit(main())

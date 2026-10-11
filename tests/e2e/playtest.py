#!/usr/bin/env python3
"""Playtest harness: sets up a scenario for a fork feature in a fresh game, then hands it to you.

    python3 tests/e2e/playtest.py --list
    python3 tests/e2e/playtest.py <scenario> [--tiles] [--scheme modern|classic] [--no-attach]

The game starts headless in tmux with the curses binary, the scenario's Lua builds the situation
next to the player, and then:
  - by default you are attached to the tmux session and play in your terminal (Ctrl+B D detaches);
  - with --tiles the game is saved and reopened in the tiles binary, in a normal window;
  - with --no-attach the screen is printed and the session closed (for checking scenarios).
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import HELPERS, settle  # noqa: E402
from tmux_game import ROOT, Game, start_new_game  # noqa: E402
ZOMBIE = "gapi.place_monster_at(MonsterTypeId.new('{id}'), here({x},{y})) "

SCENARIOS = [
    {
        "id": "quick_stack",
        "about": "Quick stack (Q) puts carried items into nearby storage that already holds them",
        "setup": "arena() spawn(2,0,'usb_drive',1,'f_rack') give('usb_drive',3) give('plastic_six_dice',1) ",
        "check": [
            "Press Q (modern scheme): the three USB drives join the rack two tiles east.",
            "The dice stay in your inventory: nothing nearby holds dice.",
            "The log says 'Stashed N items into 1 spot'.",
        ],
    },
    {
        "id": "sort_pile",
        "about": "Sort pile (Z) moves the pile under you onto matching shelves",
        "setup": "arena() spawn(3,0,'usb_drive',1,'f_rack') spawn(-3,0,'flyer',1,'f_rack') "
                 "spawn(0,0,'usb_drive',2) spawn(0,0,'character_sheet',1) spawn(0,0,'plastic_six_dice',1) ",
        "check": [
            "Press Z: the USB drives go to the east rack, the character sheet to the west rack (books).",
            "The dice stay on your tile.",
        ],
    },
    {
        "id": "combine",
        "about": "Combine partly used tools (matchbooks with 5 and 7 matches)",
        "setup": "arena() local u=gapi.get_avatar() u:create_item(ItypeId.new('matches'),1):set_charges(5) "
                 "u:create_item(ItypeId.new('matches'),1):set_charges(7) ",
        "check": [
            "Open the inventory (i), select a matchbook, press C (Combine).",
            "One matchbook with 12 matches remains; the log says 'You combine 2 matchbooks into one.'",
        ],
    },
    {
        "id": "folded_items",
        "about": "Black powder rounds stack with factory rounds; different rings share one line",
        "setup": "arena() local p=here(1,0) M:create_item_at(p, ItypeId.new('9mm'), 20) "
                 "local it=gapi.create_item(ItypeId.new('9mm'), 10) it:set_var_str('stack_mod:black_powder','10') "
                 "M:add_item(p, it) local u=gapi.get_avatar() for _,v in ipairs({'ruby_gold_ring','copper_ring'}) do "
                 "local r=gapi.create_item(ItypeId.new('jewelry_ring'), -1) r:set_var_str('variant',v) u:add_item(r) end ",
        "check": [
            "Look at the tile east of you (l): one stack of 30 9mm rounds, '10 black powder' in its name.",
            "Open the inventory (i): both rings share one line, each keeps its own name and price.",
        ],
    },
    {
        "id": "hud",
        "about": "Weather and weapon boxes on the map, stance line, aligned sidebar, body panel",
        "setup": "arena() give('bat',1) gapi.get_avatar():add_effect(EffectTypeId.new('bleed'), "
                 "TimeDuration.from_turns(30), BodyPartTypeId.new('arm_l')) ",
        "check": [
            "Top-left boxes: weather and time; what you fight with, your style and stance.",
            "Sidebar rows share one label column; the Body panel lists the bleeding arm. H opens details.",
            "Options > Interface > Weather box / Weapon box move the boxes or turn them off.",
        ],
    },
    {
        "id": "targeting",
        "about": "Aiming starts on the reachable hostile and warns about an ally in the line of fire",
        "setup": "arena() local u=gapi.get_avatar() u:add_item(gapi.create_item(ItypeId.new('model_10_revolver'), -1)) "
                 "u:add_item(gapi.create_item(ItypeId.new('38_special'), 12)) "
                 + ZOMBIE.format(id="mon_zombie", x=6, y=0)
                 + "local d=gapi.place_monster_at(MonsterTypeId.new('mon_dog'), here(3,0)) d:make_friendly() "
                 + ZOMBIE.format(id="mon_zombie_rot", x=-6, y=0),
        "check": [
            "Wield the revolver (h) and reload it (r).",
            "Press f: aiming starts on the decayed zombie to the west, whose line is clear.",
            "Tab to the east zombie: the panel says 'Ally in the line of fire: <dog>'.",
            "Hover a zombie with the mouse: the hint says what a click does.",
        ],
    },
    {
        "id": "loudness",
        "about": "Gun info shows how loud a shot is",
        "setup": "arena() give('m9',1) give('model_10_revolver',1) ",
        "check": [
            "Open the inventory, pick a gun, read its info: 'Loudness: N (loud|very loud|...)'.",
        ],
    },
    {
        "id": "sound_markers",
        "about": "A zombie walks behind a wall: its footsteps leave '?' markers that fade",
        "setup": "arena() for dy=-9,9 do M:set_ter_at(here(6,dy), TerId.new('t_wall'):int_id()) "
                 "for dx=7,9 do M:set_ter_at(here(dx,dy), TerId.new('t_floor'):int_id()) "
                 "M:set_furn_at(here(dx,dy), FurnId.new('f_null'):int_id()) end end "
                 + ZOMBIE.format(id="mon_zombie", x=8, y=6)
                 + "gapi.get_monster_at(here(8,6)):wander_to(here(8,-8), 100) ",
        "check": [
            "Wait a few turns (x): '?' markers appear east of the wall and dim as they age.",
            "Options > Interface > Sound marker turns sets how long they stay (1 = upstream).",
        ],
    },
    {
        "id": "safe_mode",
        "about": "Smart safe mode ignores a zombie locked in a glass cell, not one that can reach you",
        "options": {"SAFEMODE": "true"},
        "setup": "arena() for dx=-1,1 do for dy=-1,1 do if dx ~= 0 or dy ~= 0 then "
                 "M:set_ter_at(here(6+dx,dy), TerId.new('t_reinforced_glass'):int_id()) end end end "
                 + ZOMBIE.format(id="mon_zombie", x=6, y=0),
        "check": [
            "Press n (auto-explore) or walk away: safe mode does not stop you for the caged zombie.",
            "Smash the glass or let another zombie in: now safe mode stops you.",
        ],
    },
    {
        "id": "stances",
        "about": "F2 run, F3 crouch, F4 prone (modern scheme); the weapon box shows the stance",
        "setup": "arena() ",
        "check": [
            "Press F2, F3, F4 and watch the stance line in the weapon box and the Movement row.",
            "\" opens the movement mode menu in both schemes.",
        ],
    },
    {
        "id": "contextual",
        "about": "Space does the one sensible action next to you, or lists the choices",
        "setup": "arena() M:set_ter_at(here(1,0), TerId.new('t_door_c'):int_id()) "
                 "M:set_ter_at(here(-3,0), TerId.new('t_door_c'):int_id()) spawn(-3,2,'rock',2) ",
        "check": [
            "Press Space: the door east of you opens without a direction prompt; Space again closes it.",
            "Walk next to the west door and the rocks: Space lists what each direction does.",
            "u opens the use menu on the item you used last.",
        ],
    },
    {
        "id": "crafting",
        "about": "Crafting says what is missing and jumps to a part you can make",
        "setup": "arena() give('string_6',6) ",
        "check": [
            "Open crafting (k), filter (f) 'short rope'.",
            "The recipe panel starts with 'Missing: ...'; long string is tagged '(can make)'.",
            "Press p (modern scheme): the list jumps to the long string recipe.",
        ],
    },
    {
        "id": "status_effects",
        "about": "Tiles: bleeding, poisoned and stunned creatures show looping overlays (use --tiles)",
        "setup": "arena() "
                 + ZOMBIE.format(id="mon_zombie", x=2, y=0)
                 + "local a=gapi.get_monster_at(here(2,0)) a:make_friendly() "
                 "a:add_effect(EffectTypeId.new('bleed'), TimeDuration.from_turns(600)) "
                 + ZOMBIE.format(id="mon_zombie", x=-2, y=1)
                 + "local b=gapi.get_monster_at(here(-2,1)) b:make_friendly() "
                 "b:add_effect(EffectTypeId.new('poison'), TimeDuration.from_turns(600)) "
                 + ZOMBIE.format(id="mon_zombie", x=0, y=-2)
                 + "local c=gapi.get_monster_at(here(0,-2)) c:make_friendly() "
                 "c:add_effect(EffectTypeId.new('stunned'), TimeDuration.from_turns(600)) ",
        "check": [
            "In the tiles window: a falling blood drip, a bobbing poison icon and dizzy stars loop.",
            "Options > Graphics > Status effect animations turns them off.",
        ],
    },
]


def tiles_binary():
    for candidate in (ROOT / "out" / "build" / "linux-full" / "src" / "cataclysm-bn-tiles",
                      ROOT / "cataclysm-bn-tiles"):
        if candidate.exists():
            return candidate
    raise SystemExit("cataclysm-bn-tiles not found; build the tiles target first")


def prepare(scenario, scheme):
    userdir = Path("/tmp/bn-playtest") / scenario["id"]
    shutil.rmtree(userdir, ignore_errors=True)
    options = {"SAFEMODE": "false", **scenario.get("options", {})}
    if scheme:
        options["CONTROL_SCHEME"] = scheme
    g = Game(name=f"bn-playtest-{scenario['id']}", options=options, userdir=userdir)
    start_new_game(g)
    settle(g)
    g.define_lua(HELPERS)
    result = g.lua(scenario["setup"] + "out('done')")
    if not result or result[-1] != "done":
        print(g.screen())
        g.close()
        raise SystemExit(f"scenario setup failed: {result}")
    settle(g)
    return g


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenario", nargs="?")
    parser.add_argument("--list", action="store_true", help="list the scenarios")
    parser.add_argument("--tiles", action="store_true", help="reopen the prepared game in the tiles binary")
    parser.add_argument("--scheme", choices=["modern", "classic"], help="control scheme (default: modern)")
    parser.add_argument("--no-attach", action="store_true", help="print the screen and close instead of attaching")
    args = parser.parse_args()

    by_id = {s["id"]: s for s in SCENARIOS}
    if args.list or not args.scenario:
        for s in SCENARIOS:
            print(f"  {s['id']:<16} {s['about']}")
        return 0
    if args.scenario not in by_id:
        raise SystemExit(f"unknown scenario {args.scenario!r}; see --list")
    scenario = by_id[args.scenario]

    g = prepare(scenario, args.scheme)
    print(f"\n{scenario['id']}: {scenario['about']}\nWhat to check:")
    for line in scenario["check"]:
        print(f"  - {line}")
    print(f"Game data: {g.userdir}\n")

    if args.no_attach:
        print(g.screen())
        g.close()
        return 0
    if args.tiles:
        g.keys("Escape", delay=0.5)
        g.keys("S", delay=1)
        g.keys("y", "Enter", delay=1)
        g.wait_for("[Load]", timeout=60)
        subprocess.run(["tmux", "kill-session", "-t", g.name], stderr=subprocess.DEVNULL)
        world = next(p.name for p in (g.userdir / "save").iterdir() if p.is_dir())
        # The tiles binary loads the first save of the world given by --world.
        return subprocess.run([str(tiles_binary()), "--basepath", f"{ROOT}/", "--userdir", f"{g.userdir}/",
                               "--world", world], cwd=ROOT).returncode
    if sys.stdin.isatty() and "TMUX" not in os.environ:
        os.execvp("tmux", ["tmux", "attach", "-t", g.name])
    print(f"Attach with: tmux attach -t {g.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

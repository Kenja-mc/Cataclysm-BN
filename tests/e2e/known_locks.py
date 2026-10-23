"""Known locked doors: only an attempted door is remembered, survives save, clears when opened.

The curses game plays the fixture with real input: two identical locked doors, then an open
attempt on the east one.  Map knowledge is read back from the real player database after a
real save, so the check exercises the shipped save format rather than injected state.

`analyse_known_lock_icons` is the narrow pixel check for the tiles harness in tiles.py: it
compares captures of the same saved world with the display option off and on.
"""
import json
import sqlite3
import zlib
from dataclasses import dataclass
from pathlib import Path

from helpers import HELPERS, arena, save_and_quit, settle, start_new_game, wait_until
from tmux_game import Game, in_game
from vehicle_box import spawn_vehicle, vehicle_game

EAST_DOOR = (1, 0)
NORTH_DOOR = (0, -1)
MM_REG_SIZE = 8
SEEX = SEEY = 12
TILES_PER_REGION = MM_REG_SIZE * SEEX


@dataclass(frozen=True)
class LockTile:
    """One memorized locked-door tile, in absolute map-square coordinates."""
    x: int
    y: int
    z: int
    kind: str


def _world_dir(game):
    saves = [p for p in (game.userdir / "save").iterdir() if p.is_dir()]
    assert len(saves) == 1, f"expected one saved world, found {saves}"
    return saves[0]


def _region_index(path, submap_index, tile_index):
    """Turn a .mmr file name, region submap index and submap tile index into absolute tiles."""
    stem = Path(path).name.removesuffix(".mmr")
    try:
        rx, ry, rz = (int(part) for part in stem.split(".")[-3:])
    except ValueError as exc:
        raise AssertionError(f"unexpected memory map file name {path!r}") from exc
    sub_y, sub_x = divmod(submap_index, MM_REG_SIZE)
    tile_y, tile_x = divmod(tile_index, SEEX)
    return (rx * TILES_PER_REGION + sub_x * SEEX + tile_x,
            ry * TILES_PER_REGION + sub_y * SEEY + tile_y,
            rz)


def _locks_from_region(path, raw):
    found = []
    region = json.loads(raw)
    assert isinstance(region, list), f"{path}: memory map region is not an array"
    for submap_index, submap in enumerate(region):
        if not isinstance(submap, list) or not submap or not isinstance(submap[0], dict):
            continue
        metadata = submap[0]
        for member, kind in (("locked_terrain", "terrain"), ("locked_vehicle", "vehicle")):
            for tile_index in metadata.get(member, []):
                x, y, z = _region_index(path, submap_index, tile_index)
                found.append(LockTile(x, y, z, kind))
    return found


def lock_knowledge(game):
    """Read every memorized locked door from the saved player database."""
    found = []
    world = _world_dir(game)
    for db_path in sorted(world.glob("*.sqlite3")):
        if db_path.name == "map.sqlite3":
            continue
        connection = sqlite3.connect(db_path)
        try:
            rows = connection.execute(
                "SELECT path, data, compression FROM files WHERE path LIKE '%.mmr'").fetchall()
        finally:
            connection.close()
        for path, data, compression in rows:
            raw = bytes(data)
            if compression == "zlib":
                raw = zlib.decompress(raw)
            found.extend(_locks_from_region(path, raw))
    if not found:
        # Older worlds keep the same JSON in .mm1 files instead of the player database.
        for path in sorted(world.rglob("*.mmr")):
            found.extend(_locks_from_region(str(path), path.read_bytes()))
    return found


def save_and_read_locks(game):
    assert game.lua("out(gdebug.save_game())") == ["true"], "saving the game failed:\n" + game.screen()
    return lock_knowledge(game)


def abs_pos(game):
    return tuple(int(value) for value in game.lua("pos()")[0].split(","))


def start_lock_game(name, scheme):
    game = Game(name=name, options={
        "CONTROL_SCHEME": scheme, "SAFEMODE": "false",
        "SHOW_WELCOME": "false", "SHOW_TIPS": "false",
    })
    start_new_game(game)
    game.define_lua(HELPERS)
    return game


def two_locked_doors(game):
    arena(game)
    assert game.lua(
        "M:set_ter_at(here(1,0),TerId.new('t_door_locked'):int_id()) "
        "M:set_ter_at(here(0,-1),TerId.new('t_door_locked'):int_id()) out('ok')") == ["ok"]
    settle(game)
    for dx, dy in (EAST_DOOR, NORTH_DOOR):
        assert game.lua(f"M:get_ter_at(here({dx},{dy})):str_id():str()") == ["t_door_locked"]


def attempt_open_east(game):
    position, clock = abs_pos(game), game.lua(
        "out(gapi.current_turn():to_turn(), -gapi.get_avatar():get_moves())")[0]
    game.keys("o", "l", delay=0.3)
    assert wait_until(lambda: "door is locked" in game.screen(), 5), game.screen()
    assert abs_pos(game) == position, "a failed open attempt must not move the avatar"
    assert game.lua(
        "out(gapi.current_turn():to_turn(), -gapi.get_avatar():get_moves())")[0] == clock, \
        "a failed open attempt must not cost moves"
    assert game.lua("M:get_ter_at(here(1,0)):str_id():str()") == ["t_door_locked"]


def test_only_attempted_locked_door_is_remembered(_g):
    game = start_lock_game("bn-e2e-known-locks", "classic")
    try:
        two_locked_doors(game)
        avatar = abs_pos(game)
        assert game.lua("out(gdebug.save_game())") == ["true"], "saving the pristine fixture failed"
        assert lock_knowledge(game) == [], "untried doors must not be marked"

        attempt_open_east(game)
        locks = save_and_read_locks(game)
        east = LockTile(avatar[0] + EAST_DOOR[0], avatar[1] + EAST_DOOR[1], avatar[2], "terrain")
        assert locks == [east], f"expected only the attempted east door, got {locks}"

        # Real quit, resume and load; then a fresh save must still carry the marker.
        save_and_quit(game)
        assert game.wait_for("MAIN MENU", timeout=60), game.screen()
        game.keys("Enter", delay=1)  # the cursor defaults to Load when saves exist
        assert game.wait_for("Load character from", timeout=30), game.screen()
        game.keys("Enter", delay=1)  # the only character
        assert wait_until(lambda: in_game(game.screen()), 60), "resume did not reach the game"
        game.define_lua(HELPERS)
        assert abs_pos(game) == avatar, "resume loaded the wrong character position"
        assert game.lua("M:get_ter_at(here(1,0)):str_id():str()") == ["t_door_locked"], \
            "the resumed world must keep the door locked"
        assert save_and_read_locks(game) == [east], \
            "lock knowledge did not survive quit, resume and save"
    finally:
        game.close()


def test_opening_the_attempted_door_clears_the_marker(_g):
    game = start_lock_game("bn-e2e-known-locks-clear", "classic")
    try:
        two_locked_doors(game)
        avatar = abs_pos(game)
        attempt_open_east(game)
        east = LockTile(avatar[0] + EAST_DOOR[0], avatar[1] + EAST_DOOR[1], avatar[2], "terrain")
        assert save_and_read_locks(game) == [east]

        # Step through the wall into the room and give it a roof, so the locked door's
        # OPENCLOSE_INSIDE rule lets the avatar open it from inside; this is the real
        # successful open path in map::open_door_ter.
        assert game.lua(
            "local a=gapi.get_avatar() local p=here(2,0) "
            "a:set_pos_ms(p) "
            "M:set_ter_at(TripointBubMs.new(p.x,p.y,p.z+1),"
            "TerId.new('t_flat_roof'):int_id()) "
            "out(not M:is_outside(p))") == ["true"], \
            "the avatar must stand inside before the inside-open rule applies"
        settle(game)

        game.keys("o", "h", delay=0.3)
        # The avatar now stands east of the door, so the door is one tile west.
        assert wait_until(lambda: game.lua(
            "out(M:get_ter_at(here(-1,0)):str_id():str())") == ["t_door_o"], 10), game.screen()
        assert save_and_read_locks(game) == [], "opening a known locked door must clear its marker"
    finally:
        game.close()


def _nearest_locked_vehicle_door(game):
    """Find an OPENABLE+DOOR_LOCKING vehicle tile and return its offset from the vehicle origin."""
    reported = game.lua(
        "local o=gapi.get_avatar():get_pos_ms() local r={} "
        "for dx=-3,3 do for dy=-3,3 do "
        "local p=TripointBubMs.new(o.x+dx,o.y+dy,o.z) "
        "if M:has_vehicle_part_with_feature_at(p,'DOOR_LOCKING') and "
        "M:has_vehicle_part_with_feature_at(p,'OPENABLE') then r[#r+1]=dx..','..dy end "
        "end end out(table.concat(r,';'))")
    offsets = [tuple(int(value) for value in entry.split(",")) for entry in reported[0].split(";")
               if entry]
    assert offsets, "the spawned car has no locked door parts:\n" + game.screen()
    return min(offsets, key=lambda offset: abs(offset[0]) + abs(offset[1]))


def test_vehicle_locked_door_knowledge_follows_attempts(_g):
    # Undamaged debug spawn: locked doors and a vehicle that still needs hotwiring.
    game = vehicle_game("bn-e2e-known-locks-vehicle", CONTROL_SCHEME="classic")
    try:
        spawn_vehicle(game)
        origin = abs_pos(game)
        assert save_and_read_locks(game) == [], "an untried locked vehicle door must not be marked"

        dx, dy = _nearest_locked_vehicle_door(game)
        # Stand one tile west of the door and try to open it eastwards.
        assert game.lua(
            f"local o=gapi.get_avatar():get_pos_ms() "
            f"local p=TripointBubMs.new(o.x+{dx - 1},o.y+{dy},o.z) "
            f"gapi.get_avatar():set_pos_ms(p) out('ok')") == ["ok"]
        settle(game)
        game.keys("o", "l", delay=0.3)
        assert wait_until(lambda: "is locked" in game.screen(), 10), game.screen()

        door = LockTile(origin[0] + dx, origin[1] + dy, origin[2], "vehicle")
        locks = save_and_read_locks(game)
        assert locks == [door], f"only the attempted vehicle door should be remembered, got {locks}"

        # Real bound fixture: replace with the same car without lock parts, then open for real.
        assert game.lua(
            "local v=M:get_vehicles()[1] local p=v:pos() "
            "out(M:replace_vehicle(p,'car',{locks=false}))") == ["true"]
        settle(game)
        game.keys("o", "l", delay=0.3)
        assert save_and_read_locks(game) == [], \
            "successfully opening the unlocked vehicle door must clear the marker"
    finally:
        game.close()


def _change_one_option_and_save(game):
    """Open the options menu, flip any visible boolean, save, and return the written options."""
    from options_menu import open_options

    open_options(game)
    rows = [y for y, line in enumerate(game.screen().splitlines())
            if "│ True " in line or "│ False " in line]
    assert rows, "a boolean option must be on the first page\n" + game.screen()
    y = rows[0]
    line = game.screen().splitlines()[y]
    value_x = line.index("│ True") + 2 if "│ True" in line else line.index("│ False") + 2
    game.click(value_x, y)
    game.keys("Escape", delay=0.6)
    assert wait_until(lambda: "Save changes?" in game.screen(), 10), game.screen()
    game.keys("y", delay=1)
    path = game.userdir / "config" / "options.json"
    assert wait_until(lambda: path.exists(), 5)
    return {entry["name"]: entry["value"] for entry in json.loads(path.read_text())}


def test_lock_icon_option_follows_the_control_scheme(_g):
    for scheme, expected in (("modern", "true"), ("classic", "false")):
        game = start_lock_game(f"bn-e2e-known-locks-option-{scheme}", scheme)
        try:
            options = _change_one_option_and_save(game)
            assert options.get("KNOWN_LOCKED_DOOR_ICONS") == expected, \
                f"{scheme}: expected {expected}, got {options.get('KNOWN_LOCKED_DOOR_ICONS')}"
        finally:
            game.close()


def build_known_lock_fixture(game):
    """Build two identical locked doors and try only the east one, then save the world."""
    game.define_lua(HELPERS)
    two_locked_doors(game)
    attempt_open_east(game)
    assert game.lua("out(gdebug.save_game())") == ["true"], "saving the fixture failed:\n" + game.screen()


def build_known_lock_world(session):
    """Prepare a tiles.py Session from the attempt fixture; call before session.launch()."""
    import subprocess

    import tiles

    tiles.tmux_game.ROOT = session.root
    game = tiles.Game(name="bn-tiles-e2e-known-locks-save", userdir=session.curses_userdir,
                      options={"SAFEMODE": "false", "INITIAL_TIME": "12",
                               "CONTROL_SCHEME": "classic"})
    try:
        tiles.start_new_game(game)
        build_known_lock_fixture(game)
        (session.artifacts / "known-locks-curses.txt").write_text(game.screen_colors())
    finally:
        subprocess.run(["tmux", "kill-session", "-t", game.name],
                       stderr=subprocess.DEVNULL, check=False)
    saves = [p for p in (session.curses_userdir / "save").iterdir() if p.is_dir()]
    assert len(saves) == 1, f"expected one saved world, found {saves}"
    session.world = saves[0].name


@dataclass(frozen=True)
class LockCheck:
    name: str
    ok: bool
    detail: str


def analyse_known_lock_icons(off_png, on_png, attempted_tile, untried_tile, artifacts):
    """Pixel proof for tiles.py: only the attempted door changes when the icons are enabled.

    attempted_tile and untried_tile are (x0, y0, x1, y1) pixel rectangles around the two
    identical doors.  The off capture is the same saved world with the option false; the on
    capture has it true.  Returns a list of LockCheck; the caller turns them into its report.
    """
    import tiles  # local import keeps the curses tests usable without the tiles dependencies

    checks = []
    w, h, off = tiles.frame_rgb(off_png)
    w2, h2, on = tiles.frame_rgb(on_png)
    checks.append(LockCheck("captures have the same size", (w, h) == (w2, h2),
                            f"{w}x{h} vs {w2}x{h2}"))
    if (w, h) != (w2, h2):
        return checks

    def inside(x, y, rect):
        x0, y0, x1, y1 = rect
        return x0 <= x < x1 and y0 <= y < y1

    changed = []
    for y in range(h):
        row = (y * w) * 3
        for x in range(w):
            i = row + x * 3
            if off[i:i + 3] != on[i:i + 3]:
                changed.append((x, y))
    checks.append(LockCheck("enabling the icons changes pixels", bool(changed),
                            f"{len(changed)} changed pixels"))
    outside = [p for p in changed if not inside(*p, attempted_tile)]
    checks.append(LockCheck("only the attempted door changes", not outside,
                            f"{len(outside)} changed pixels outside {attempted_tile}, first "
                            f"{outside[:5]}"))
    untried_changed = [p for p in changed if inside(*p, untried_tile)]
    checks.append(LockCheck("the untried identical door stays bare", not untried_changed,
                            f"{len(untried_changed)} pixels changed inside {untried_tile}"))
    if changed:
        x0 = min(p[0] for p in changed)
        y0 = min(p[1] for p in changed)
        x1 = max(p[0] for p in changed)
        y1 = max(p[1] for p in changed)
        tiles.crop_to(on_png, {"x0": x0, "y0": y0, "w": x1 - x0 + 1, "h": y1 - y0 + 1,
                               "cx": (x0 + x1) / 2, "cy": (y0 + y1) / 2},
                      artifacts / "known-lock-marker.png")
    return checks


TESTS = [test_only_attempted_locked_door_is_remembered,
         test_opening_the_attempted_door_clears_the_marker,
         test_vehicle_locked_door_knowledge_follows_attempts,
         test_lock_icon_option_follows_the_control_scheme]

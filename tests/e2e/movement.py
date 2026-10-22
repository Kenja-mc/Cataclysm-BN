"""Walking, waiting, blocked steps, auto-explore and the control scheme files.

Tests that take `g` run on the runner's main game; the scheme tests start their own.
"""
import json
import tempfile
from pathlib import Path

from helpers import HELPERS, arena, bub_pos, exploration_arena, settle, start_new_game, wait_until
from tmux_game import Game


def test_auto_explore(g):
    """n walks toward unseen ground without a rolled NPC or monster blocking the route."""
    exploration_arena(g)
    start = bub_pos(g)
    g.keys("n", delay=0.6)
    assert wait_until(lambda: bub_pos(g) != start, timeout=15), "n should start walking:\n" + g.screen()
    assert "Auto-move canceled" not in g.screen(), g.screen()


def test_wasd_movement(g):
    arena(g)
    steps = {"d": (1, 0), "a": (-1, 0), "s": (0, 1), "w": (0, -1),
             "e": (1, -1), "z": (-1, 1), "c": (1, 1), "q": (-1, -1)}
    for key, (dx, dy) in steps.items():
        before = bub_pos(g)
        g.keys(key, delay=0.8)
        after = bub_pos(g)
        assert after == (before[0] + dx, before[1] + dy, before[2]), f"{key}: {before} -> {after}"


def test_wait_keeps_position(g):
    before = bub_pos(g)
    g.keys("x", delay=0.8)
    assert bub_pos(g) == before


def test_blocked_step_says_why(g):
    """Walking into a wall tells you what is in the way instead of silently doing nothing."""
    arena(g)
    assert g.lua("M:set_ter_at(here(1,0), TerId.new('t_wall'):int_id()) out('ok')") == ["ok"]
    before = bub_pos(g)
    g.keys("d", delay=0.8)
    assert bub_pos(g) == before
    assert "is in the way" in g.screen(), g.screen()


def test_classic_control_scheme(g):
    """Options → Control scheme → Classic brings back vi-keys and bump attacks."""
    classic = Game(name="bn-e2e-classic", options={"SAFEMODE": "false", "CONTROL_SCHEME": "classic"})
    try:
        start_new_game(classic)
        classic.keys(".", delay=0.6)
        classic.define_lua(HELPERS)
        arena(classic)
        for key, (dx, dy) in {"l": (1, 0), "k": (0, -1), "h": (-1, 0), "j": (0, 1)}.items():
            before = bub_pos(classic)
            classic.keys(key, delay=0.8)
            assert bub_pos(classic) == (before[0] + dx, before[1] + dy, before[2]), key
        assert "wasd move" not in classic.screen()
        # Bump attacks come with the scheme even though options.json only names the scheme.
        assert classic.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(1,0)) out('ok')") == ["ok"]
        before = zombie_hp(classic)
        for _ in range(6):
            classic.keys("l", delay=1)
            if zombie_hp(classic) != before:
                break
        assert zombie_hp(classic) != before, "walking into a zombie attacks it in classic"
    finally:
        classic.close()


def test_old_full_keybindings_file(g):
    """Older versions saved every binding; such a file must not undo the modern scheme."""
    import json, tempfile
    # What upstream's save() wrote: every action of every context, with id, category and bindings.
    dump = [{"id": e["id"], "category": e.get("category", "default"), "bindings": e["bindings"]}
            for e in json.load(open("data/raw/keybindings/keybindings.json")) if "bindings" in e]
    path = Path(tempfile.mkdtemp()) / "keybindings.json"
    path.write_text(json.dumps(dump))
    old = Game(name="bn-e2e-oldkeys", options={"SAFEMODE": "false"}, keybindings=str(path))
    try:
        start_new_game(old)
        old.define_lua(HELPERS)
        settle(old)
        arena(old)
        for key, (dx, dy) in {"d": (1, 0), "w": (0, -1), "e": (1, -1)}.items():
            before = bub_pos(old)
            old.keys(key, delay=0.8)
            assert bub_pos(old) == (before[0] + dx, before[1] + dy, before[2]), key
        assert "wasd move" in old.screen()
    finally:
        old.close()


def zombie_hp(g):
    out = g.lua("local m=gapi.get_monster_at(here(1,0)) if m then out(m:get_hp()) else out(-1) end")
    return int(out[0])


TESTS = [
    test_auto_explore,
    test_wasd_movement,
    test_wait_keeps_position,
    test_blocked_step_says_why,
    test_classic_control_scheme,
    test_old_full_keybindings_file,
]

"""The crafting screen: opening on content, part chains and recrafting after a reload.

Tests that take `g` run on the runner's main game; the part chain needs its own option.
"""
import re
import time

from helpers import HELPERS, Game, action_menu, arena, count_at, count_carried, give, open_crafting, save_and_quit, settle, spawn, start_new_game, wait_until


def craft_by_name(g, name):
    open_crafting(g)
    g.keys("f", delay=0.8)
    g.type(name)
    g.keys("Enter", delay=1.5)
    for _ in range(3):
        if "Searched" not in g.screen():
            break
        g.keys("Enter", delay=1.5)


def load_first_save(g, timeout=120):
    """After save-and-quit the main menu reopens on Load; Enter picks the world, then the character."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = g.screen()
        if "X,Y,Z" in s and " move " in s:
            return
        if "»" in s:
            g.keys("Enter", delay=2)
        else:
            time.sleep(0.5)
    raise AssertionError("could not load the save\n" + g.screen())


def test_crafting_opens_on_content(g):
    open_crafting(g)
    s = g.screen()
    g.keys("Escape", delay=0.6)
    assert "< FAVORITE >" not in s, "crafting should not open on the empty favorites list"


def test_recraft_after_reload(g):
    """Upstream #10083: recraft crashed after save, quit to menu and reload in one session."""
    # This crafting fixture does not need idling world vehicles across the reload.
    assert g.lua("for _,v in ipairs(M:get_vehicles()) do "
                 "if v:type() ~= 'bicycle' then M:replace_vehicle(v,'bicycle') end end "
                 "local passive=true for _,v in ipairs(M:get_vehicles()) do "
                 "passive=v:type()=='bicycle' and passive end out(passive)") == ["true"]
    # Materials on the floor nearby also exercise the larger crafting reach.
    arena(g)
    spawn(g, 3, 0, "glass_shard", 3)
    settle(g)
    craft_by_name(g, "glass shard trap")
    # A heavily loaded character puts the result on the ground; either way it was crafted.
    made = lambda: count_carried(g, "glass_shard_trap") + count_at(g, 0, 0, "glass_shard_trap")
    assert wait_until(lambda: made() == 1), g.screen()
    save_and_quit(g)
    load_first_save(g)
    g.define_lua(HELPERS)
    action_menu(g, "Craft", "Recraft last recipe")
    assert wait_until(lambda: made() == 2), g.screen()


DURATION = (r"\d+ (?:seconds?|minutes?|hours?|days?|weeks?)"
            r"(?: and \d+ (?:seconds?|minutes?|hours?|days?|weeks?))?")


def flat_text(g):
    return " ".join(g.screen().split())


def test_craft_parts_chain(_g):
    """Known blockers, charged part quantities and producer timing stay consistent."""
    g = Game(name="bn-e2e-craft-parts",
             options={"SAFEMODE": "false", "CRAFTING_PART_CHAINS": "true"})
    try:
        start_new_game(g)
        g.define_lua(HELPERS)
        assert g.lua(
            "local a=gapi.get_avatar() a:clear_bionics() a:clear_mutations() "
            "a:clear_morale() a:drop_all_items() "
            "a:set_mutation(MutationBranchId.new('DEBUG_STORAGE')) "
            "for _,id in ipairs({'tinfoil_hat','handrolled_cig','rolling_paper'}) do "
            "a:learn_recipe(RecipeId.new(id)) end out('prepared')"
        ) == ["prepared"]
        arena(g)
        settle(g)

        def browse_recipe(name):
            open_crafting(g)
            g.wait_for("[f]ilter", timeout=10)
            g.keys("f", delay=0.8)
            g.wait_for("Search:", timeout=10)
            g.type(name)
            g.keys("Enter", delay=1.5)

        def close_recipes():
            g.keys("Escape", delay=0.8)

        def recipe_summary():
            """Join wrapped recipe text without neighboring list and item columns."""
            g.wait_for("Time to complete:", timeout=10)
            lines = g.screen().splitlines()
            column = next(line.index("Time to complete:") for line in lines if "Time to complete:" in line)
            return " ".join(line[column:].split("  ", 1)[0].strip() for line in lines)

        browse_recipe("tinfoil hat")
        screen = flat_text(g)
        assert "aluminum foil" in screen, screen
        assert "parts:" not in screen, screen
        assert "Part:" not in screen and "Part (blocked):" not in screen, screen
        close_recipes()

        give(g, "tobacco", 20)
        settle(g)
        browse_recipe("hand-rolled cigarette")
        screen = flat_text(g)
        assert "parts:known" in screen, screen
        assert "Part (blocked):" in screen, screen
        blocked = screen.split("Part (blocked):", 1)[1]
        paper = re.search(r"Missing:\s*(?:(\d+)\s+paper|paper\s*\((\d+)\))", blocked)
        assert paper and int(paper.group(1) or paper.group(2)) == 1, screen
        close_recipes()

        give(g, "paper", 12)
        settle(g)
        browse_recipe("hand-rolled cigarette")
        assert "parts:make" in flat_text(g), g.screen()
        g.keys("b", delay=1)
        g.keys("Home", delay=0.2)
        for _ in range(11):
            g.keys("Down", delay=0.4)
        part = re.search(r"Part: rolling paper \(make (\d+) more, ~(" + DURATION + r")\)",
                         recipe_summary())
        assert part, g.screen()
        assert part.group(1) == "12", g.screen()

        g.keys("p", delay=1.5)
        assert "rolling paper" in flat_text(g).lower(), g.screen()
        g.keys("b", delay=1)
        g.keys("Home", delay=0.2)
        g.keys("Down", delay=0.8)
        made = re.search(r"Time to complete:\s*(" + DURATION + r")", recipe_summary())
        assert made, g.screen()
        assert made.group(1) == part.group(2), g.screen()
        close_recipes()
    finally:
        g.close()


TESTS = [
    test_crafting_opens_on_content,
    test_recraft_after_reload,
    test_craft_parts_chain,
]

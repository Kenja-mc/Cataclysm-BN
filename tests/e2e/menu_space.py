"""Space in Modern menus: selects the highlighted entry, exactly like Enter.

Covers the title menu, generic UiList menus, and menu filtering; Classic keeps
its own bindings (covered in pickup_flow) and text entry keeps its spaces.
"""
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

from tmux_game import Game


def boot_to_title(g, timeout=240):
    """Fresh user dir: answer the language prompt, close the welcome popup, reach the title.

    A cold boot can sit on an unpainted blocking popup; a Space on a blank screen
    dismisses it the same way the error-popup helper does. Once real content is
    drawn, only the known prompts are answered, so nothing is confirmed blindly.
    """
    deadline = time.time() + timeout
    nudges = 0
    while time.time() < deadline:
        s = g.screen()
        if "Select your language" in s:
            g.keys("1", delay=0.6)
            continue
        if "Welcome to Bright Nights" in s:
            g.keys("Escape", delay=0.6)
            continue
        if "[New Game]" in s or "[MOTD]" in s:
            return
        if "Are you SURE" in s:
            g.keys("Escape", delay=0.6)
            continue
        if not s.strip() and nudges < 10:
            nudges += 1
            g.keys("Space", delay=0.6)
            continue
        time.sleep(0.2)
    raise AssertionError(f"never reached the title menu\n{g.screen()}")


def query_uilist(g, title, adds, drive):
    """Opens a Lua UiList, lets `drive` interact with it, returns the chosen retval."""
    body = f"local menu=UiList.new() menu:title('{title}') {' '.join(adds)} out(menu:query())"
    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(g.lua, body)
        g.wait_for(f"< {title} >")
        drive(g)
        return result.result()


def test_space_selects_the_highlighted_menu_row(g):
    adds = ["menu:add(10,'First choice')", "menu:add(20,'Second choice')",
            "menu:add(30,'Third choice')"]
    ret = query_uilist(g, "Space select", adds,
                       lambda g: g.keys("Down", "Down", "Space", delay=0.5))
    assert ret == ["30"], "Space must confirm the row the cursor is on\n" + g.screen()

    ret = query_uilist(g, "Space first", adds, lambda g: g.keys("Space", delay=0.5))
    assert ret == ["10"], "Space must confirm whatever entry is highlighted\n" + g.screen()


def test_space_stays_text_in_menu_filter(g):
    adds = ["menu:add(10,'Two words only')", "menu:add(20,'Other item')"]

    def drive(g):
        g.keys("/", delay=0.5)
        g.type("two words")
        g.keys("Enter", delay=0.5)
        g.wait_gone("Other item")
        g.keys("Space", delay=0.5)

    ret = query_uilist(g, "Space filter", adds, drive)
    assert ret == ["10"], "the space inside the filter must stay text\n" + g.screen()


def test_space_opens_selected_title_entries(_g):
    g = Game(name="bn-e2e-title-space", options={"SAFEMODE": "false"})
    try:
        boot_to_title(g)
        # Settings tab: the entry list must be open before Space picks Options.
        g.keys("t", delay=0.6)
        g.wait_for("Autopickup")
        g.keys("Space", delay=1.0)
        assert "Really quit?" not in g.screen(), "Space must not quit from Settings\n" + g.screen()
        g.wait_for("Interface")
        g.keys("Escape", delay=0.8)
        g.wait_gone("Interface")
        # New Game tab: Space enters character creation on the highlighted entry.
        g.keys("n", delay=0.6)
        g.wait_for("Custom Character")
        g.keys("Space", delay=1.0)
        g.wait_for("Points left:")
    finally:
        g.close()


def test_title_space_quits_only_from_quit_selection(_g):
    g = Game(name="bn-e2e-title-quit-space", options={"SAFEMODE": "false"})
    try:
        boot_to_title(g)
        g.keys("m", delay=0.4)
        for _ in range(7):
            g.keys("Right", delay=0.3)
        g.keys("Space", delay=0.8)
        g.wait_for("Really quit?")
        # The highlight rests on No: Space answers No and returns to the title.
        g.keys("Space", delay=0.8)
        g.wait_gone("Really quit?")
        assert "[MOTD]" in g.screen(), "answering No must stay on the title\n" + g.screen()
        # Move the highlight to Yes: Space confirms and the game exits.
        g.keys("Space", delay=0.4)
        g.wait_for("Really quit?")
        g.keys("Left", delay=0.4)
        g.keys("Space", delay=0.8)
        deadline = time.time() + 20
        while time.time() < deadline:
            if subprocess.run(["tmux", "has-session", "-t", g.name],
                              capture_output=True).returncode != 0:
                break
            time.sleep(0.3)
        else:
            raise AssertionError("answering Yes must quit the game\n" + g.screen())
    finally:
        g.close()


TESTS = [test_space_selects_the_highlighted_menu_row, test_space_stays_text_in_menu_filter,
         test_space_opens_selected_title_entries, test_title_space_quits_only_from_quit_selection]

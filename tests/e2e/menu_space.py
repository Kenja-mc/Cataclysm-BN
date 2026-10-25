"""Space in Modern menus: selects the highlighted entry, exactly like Enter.

Modern puts Space on the shared CONFIRM default, so every menu that registers
CONFIRM gets it (a Lua UiList, the title menu, the Yes/No highlight) without a
binding per context, and Space leaves the shared QUIT so it can no longer cancel
those menus. The string inputs named in the handoff (uilist filter, keybinding
search, world naming, the Lua console) keep their spaces as text. Classic keeps
its own bindings (covered in pickup_flow).
"""
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

from helpers import wait_until
from menu_scrollbars import find_scrollbar, open_main_menu
from options_menu import bool_rows, value_at
from tmux_game import Game


def boot_to_title(g, timeout=240):
    """Fresh user dir: answer the language prompt, close the welcome popup, reach the title.

    A cold boot can sit on an unpainted blocking popup; F5 is unbound on every screen
    on the way to the title, so it nudges the first frame without ever answering or
    confirming an unseen prompt. Once real content is drawn, only the known prompts
    are answered.
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
            g.keys("F5", delay=0.6)
            continue
        time.sleep(0.2)
    raise AssertionError(f"never reached the title menu\n{g.screen()}")


def cell_of(g, text, screen=None):
    """First screen cell holding `text`, searched across the whole width."""
    s = screen if screen is not None else g.screen()
    for y, line in enumerate(s.splitlines()):
        x = line.find(text)
        if x >= 0:
            return x, y
    return None


def tab_cell(g, label):
    """A cell inside the `[label]` hitbox on the title's tab strip."""
    s = g.screen()
    strip = next(l for l in s.splitlines() if "[MOTD]" in l)
    y = s.splitlines().index(strip)
    return strip.index(label) + 1, y


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


def test_lua_console_keeps_spaces(g):
    """The console's EDIT editor is a string editor: its spaces must arrive as text."""
    assert g.lua("out('two words')") == ["two words"], g.screen()


def test_keybinding_search_keeps_spaces(g):
    """The keybindings search shares its context with QUIT; spaces must still type."""
    open_main_menu(g)
    g.keys("4", delay=0.6)
    g.wait_for("Keybindings", timeout=15)
    bar = find_scrollbar(g.screen())
    assert bar, "the full keybinding list must be scrollable\n" + g.screen()
    top, _, x = bar

    def filter_text():
        return g.screen().splitlines()[top - 2][x + 4:]

    try:
        g.type("smash n", delay=0.2)
        assert wait_until(lambda: filter_text().startswith("smash n"), 10), (
            "the space must land in the search box, not close or ignore it\n" + g.screen())
        assert "Smash Nearby Terrain:" in g.screen(), (
            "a filter with a space must still match its action\n" + g.screen())
    finally:
        g.keys("Escape", delay=0.3)
        g.wait_gone("Keybindings")


def test_space_opens_selected_title_entries(_g):
    g = Game(name="bn-e2e-title-space", options={"SAFEMODE": "false"})
    try:
        boot_to_title(g)
        # Settings tab: the entry list must be open before Space picks Options.
        g.keys("T", delay=0.6)
        g.wait_for("Autopickup")
        g.keys("Space", delay=1.0)
        assert "Really quit?" not in g.screen(), "Space must not quit from Settings\n" + g.screen()
        g.wait_for("Interface")
        x, y = bool_rows(g)[0]
        g.hover(x, y)
        before = value_at(g, y)
        g.keys("Space", delay=0.3)
        assert value_at(g, y) != before, "Space must change the highlighted option"
        g.keys("Space", delay=0.3)
        assert value_at(g, y) == before, "a second Space must restore the boolean option"
        g.keys("Escape", delay=0.8)
        g.wait_gone("Interface")
        # New Game tab: Space enters character creation on the highlighted entry.
        g.keys("N", delay=0.6)
        g.wait_for("Custom Character")
        g.keys("Up", delay=0.6)  # boot highlights Preset; move to Custom Character first
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
        # No closed the prompt without leaving Quit, so Space asks again; move to Yes.
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


def test_title_mouse_hover_and_click(_g):
    g = Game(name="bn-e2e-title-mouse", options={"SAFEMODE": "false"})
    try:
        boot_to_title(g)
        # Hovering a tab moves the highlight only: the settings list appears, nothing opens.
        x, y = tab_cell(g, "Settings")
        g.hover(x + 2, y)
        g.wait_for("Autopickup")
        assert "Unbound keys" not in g.screen(), "hover must highlight, not activate\n" + g.screen()
        # A click on a sub-menu row selects and confirms it, like Space on that row.
        kx, ky = cell_of(g, "Keybindings")
        assert kx is not None, "the settings sub menu must be drawn\n" + g.screen()
        g.click(kx + 2, ky)
        g.wait_for("Unbound keys", timeout=15)
        g.keys("Escape", delay=0.5)
        g.wait_gone("Unbound keys")
        # A click on the Quit tab activates Quit, which asks before it exits.
        qx, qy = tab_cell(g, "Quit")
        g.click(qx + 2, qy)
        g.wait_for("Really quit?")
        g.keys("Space", delay=0.8)  # the highlight rests on No
        g.wait_gone("Really quit?")
        assert "[MOTD]" in g.screen(), "answering No must stay on the title\n" + g.screen()
    finally:
        g.close()


def test_worldgen_name_keeps_spaces(_g):
    """The world-name field shares its context with dialog keys; spaces must stay text."""
    g = Game(name="bn-e2e-worldname-space", options={"SAFEMODE": "false"})
    try:
        boot_to_title(g)
        g.keys("W", delay=0.6)
        g.wait_for("Create World")
        g.keys("Space", delay=1.0)
        g.wait_for("World Mods", timeout=30)
        g.keys("Tab", delay=1.0)
        g.wait_for("World end handling", timeout=30)
        g.keys("Tab", delay=1.0)
        g.wait_for("World Name", timeout=30)
        g.type("two words", delay=0.3)
        assert wait_until(lambda: "two words" in g.screen(), 10), (
            "the typed space must survive in the world name\n" + g.screen())
    finally:
        g.close()


TESTS = [test_space_selects_the_highlighted_menu_row, test_space_stays_text_in_menu_filter,
         test_lua_console_keeps_spaces, test_keybinding_search_keeps_spaces,
         test_space_opens_selected_title_entries, test_title_space_quits_only_from_quit_selection,
         test_title_mouse_hover_and_click, test_worldgen_name_keeps_spaces]

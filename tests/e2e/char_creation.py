"""Character creation on the smallest supported terminal."""
import re
import time

from tmux_game import Game


def test_char_creation_overview_fits_small_terminal(_g):
    """Upstream #10427: the OVERVIEW tab must show Scenario:/Profession: on an 80x24 terminal."""
    g = Game(name="bn-e2e-cc-overview", cols=80, rows=24, options={"SAFEMODE": "false"})

    def selected(word, name):
        return any(word in line and name in line for line in g.screen().splitlines())

    try:
        for _ in range(200):
            s = g.screen()
            if "Select your language" in s:
                g.keys("1", delay=0.5)
            elif "[New Game]" in s or "Play Now" in s:
                line = next((l for l in s.splitlines() if "Custom Character" in l), "")
                if "Custom Character" in line and "»" in line:
                    g.keys("Enter", delay=1)
                    break
                g.keys("Down", delay=0.2)
            elif "Welcome to Bright Nights" in s:
                g.keys("Escape", delay=1)
            elif not s.strip():
                g.keys("F5", delay=1)
            elif "World Mods" in s or "World Options" in s:
                break
            else:
                time.sleep(0.5)
        for _ in range(160):
            s = g.screen()
            if "Are you SURE you're finished" in s:
                g.keys("Left", delay=0.5)
                g.keys("Enter", delay=1.5)
            elif "How should death work" in s:
                g.keys("r", delay=1)
            elif "SCENARIO" in s and "POINTS" in s and "World" not in s:
                break
            elif "World Mods" in s:
                g.keys("Tab", "Tab", delay=1)
            elif "World Options" in s:
                g.keys("Tab", delay=1)
            else:
                time.sleep(0.5)
        for _ in range(12):
            if "<│SCENARIO│>" in g.screen():
                break
            g.keys("Tab", delay=0.7)
        for _ in range(140):
            if selected("Scenario", "Trans-Coast"):
                break
            g.keys("Down", delay=0.12)
        g.keys("Enter", delay=1)
        for _ in range(12):
            if "<│PROFESSION│>" in g.screen():
                break
            g.keys("Tab", delay=0.7)
        for _ in range(80):
            if selected("Profession", "Augmentation"):
                break
            g.keys("Down", delay=0.12)
        g.keys("Enter", delay=1)
        for _ in range(12):
            s = g.screen()
            if "Remaining points will be discarded" in s:
                g.keys("Escape", delay=0.8)
                continue
            if "finish character creation" in s or "<│OVERVIEW│>" in s:
                break
            g.keys("Tab", delay=0.7)
        s = g.screen()
        assert "Scenario:" in s, s
        assert "Profession:" in s, s
        assert re.search(r"Scenario:\s*\S", s), s
        assert re.search(r"Profession:\s*\S", s), s
    finally:
        g.close()


TESTS = [
    test_char_creation_overview_fits_small_terminal,
]

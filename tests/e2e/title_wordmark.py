from menu_space import boot_to_title
from tmux_game import Game


WORDMARK = (
    "###  #   #  #####  ####  #   #   ###   #   #  #",
    "#   # #   #  #      #   # #####  #   #  #   #  #",
    "#   #  # #   ####   ####  #   #  #####  #   #  #",
    "###    #    #####  #  #  #   #  #   #   ###   #####",
)


def test_title_wordmark_visible_on_80x25(_game):
    game = Game(name="bn-e2e-title-wordmark", cols=80, rows=25)
    try:
        boot_to_title(game)
        # The Quit tab has no submenu covering the title art.
        game.keys("Left", "Left")
        game.wait_for(WORDMARK[0])
        screen = [line.strip() for line in game.screen().splitlines()]
        missing = [row for row in WORDMARK if not any(row in line for line in screen)]
        assert not missing, f"Bright Nights Overhaul wordmark missing rows {missing!r}:\n{game.screen()}"
    finally:
        game.close()


TESTS = [test_title_wordmark_visible_on_80x25]

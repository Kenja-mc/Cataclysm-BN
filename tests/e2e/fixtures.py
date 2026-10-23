"""One tmux game per option profile, reused by the tests that ask for it.

Starting a game runs world generation and character creation, about twelve seconds.
Most tests differ only in what they set up inside the world, so a profile's game is
started by the first test that needs it and later tests rerun that profile's setup.
Every game is closed when the process ends.
"""
import atexit
import json
import os
from contextlib import contextmanager

from tmux_game import Game, start_new_game

_games = {}
_borrowers = {}
_retired = set()


def _close_all():
    if os.environ.get("BN_E2E_KEEP"):
        return
    for game in _games.values():
        game.close()
    _games.clear()


atexit.register(_close_all)


def _key(options, cols, rows, keybindings, userdir, layout):
    return json.dumps([sorted((options or {}).items()), cols, rows, str(keybindings), str(userdir), layout])


def retire(game):
    """Retire a profile, closing its game after the last active borrower exits.

    A test that changed an option in-game, or failed half-way through a menu, leaves state the
    profile's setup cannot undo; handing that game to the next borrower makes test order matter.
    """
    if _borrowers.get(game, 0):
        _retired.add(game)
        return
    for key, cached in list(_games.items()):
        if cached is game:
            del _games[key]
    game.close()


@contextmanager
def shared_game(name, options=None, cols=140, rows=45, keybindings=None, userdir=None,
                define="", setup=None, layout="labels"):
    """Borrow a profile; nested failures cannot close another caller's active game."""
    key = _key(options, cols, rows, keybindings, userdir, layout)
    game = _games.get(key)
    if game in _retired:
        raise RuntimeError(f"game profile {game.name} was retired by an active borrower")
    fresh = game is None
    if fresh:
        game = Game(name=name, cols=cols, rows=rows, options=options,
                    keybindings=keybindings, userdir=userdir, layout=layout)
        _games[key] = game
    _borrowers[game] = _borrowers.get(game, 0) + 1
    try:
        if fresh:
            start_new_game(game)
            if define:
                game.define_lua(define)
        else:
            game.dismiss_error_popup()
        if setup:
            setup(game)
        yield game
    except BaseException:
        retire(game)
        raise
    finally:
        _borrowers[game] -= 1
        if not _borrowers[game]:
            del _borrowers[game]
            if game in _retired:
                _retired.remove(game)
                retire(game)

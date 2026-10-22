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


def _close_all():
    if os.environ.get("BN_E2E_KEEP"):
        return
    for game in _games.values():
        game.close()
    _games.clear()


atexit.register(_close_all)


def _key(options, cols, rows, keybindings, userdir):
    return json.dumps([sorted((options or {}).items()), cols, rows, str(keybindings), str(userdir)])


@contextmanager
def shared_game(name, options=None, cols=140, rows=45, keybindings=None, userdir=None,
                define="", setup=None):
    """The game for this profile, with `setup` run before every test that borrows it."""
    key = _key(options, cols, rows, keybindings, userdir)
    game = _games.get(key)
    if game is None:
        game = Game(name=name, cols=cols, rows=rows, options=options,
                    keybindings=keybindings, userdir=userdir)
        start_new_game(game)
        if define:
            game.define_lua(define)
        _games[key] = game
    else:
        game.dismiss_error_popup()
    if setup:
        setup(game)
    yield game

import atexit
import json
import os
import sys
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


def _key(options, cols, rows, keybindings, userdir, layout, state_path):
    return json.dumps([sorted((options or {}).items()), cols, rows, str(keybindings), str(userdir),
                       layout, str(state_path)])


def retire(game):
    if _borrowers.get(game, 0):
        _retired.add(game)
        return
    for key, cached in list(_games.items()):
        if cached is game:
            del _games[key]
    game.close()


@contextmanager
def shared_game(name, options=None, cols=140, rows=45, keybindings=None, userdir=None,
                define="", setup=None, layout="labels", retries=1, state_path=None):
    for attempt in range(retries + 1):
        cm = _shared_game_once(name, options, cols, rows, keybindings, userdir,
                               define, setup, layout, state_path)
        try:
            game = cm.__enter__()
        except AssertionError:
            if attempt == retries:
                raise
            continue
        break
    try:
        yield game
    except BaseException:
        cm.__exit__(*sys.exc_info())
        raise
    else:
        cm.__exit__(None, None, None)


@contextmanager
def _shared_game_once(name, options, cols, rows, keybindings, userdir, define, setup, layout,
                      state_path):
    key = _key(options, cols, rows, keybindings, userdir, layout, state_path)
    game = _games.get(key)
    if game in _retired:
        raise RuntimeError(f"game profile {game.name} was retired by an active borrower")
    fresh = game is None
    if fresh:
        game = Game(name=name, cols=cols, rows=rows, options=options,
                    keybindings=keybindings, userdir=userdir, layout=layout,
                    state_path=state_path)
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

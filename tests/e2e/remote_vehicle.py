"""Remote vehicle control (upstream #5413): pressing the control-vehicle action must open
the remote vehicle's menu instead of indexing vehicles parts with -1.
"""
from helpers import HELPERS, Game, action_menu, arena, settle, start_new_game
from vehicle_box import spawn_vehicle


def open_action_menu(game, category, action):
    """The hub check reads the screen once; under load the redraw can lag, so retry it."""
    try:
        action_menu(game, category, action)
    except AssertionError:
        game.keys("Escape", delay=0.5)
        action_menu(game, category, action)


def remote_vehicle_game(name, **options):
    game = Game(name=name, options={"SAFEMODE": "false", **options})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
        # The bubble car ships drive-by-wire controls (REMOTE_CONTROLS + CONTROLS).
        spawn_vehicle(game, "bubble_car")
    except Exception:
        game.close()
        raise
    return game


def enter_remote_control(game):
    """Add bio_remote, then take control through the real UI so setremoteveh() caches it."""
    # Step off inside the same submap: a cross-submap teleport shifts the map, and the
    # shift's setremoteveh() would cache the pre-setup lookup for the rest of the turn.
    assert game.lua("gapi.get_avatar():set_pos_ms(here(-6,-6)) out('ok')") == ["ok"]
    settle(game)
    prepared = game.lua(
        "local u=gapi.get_avatar() u:clear_bionics() "
        "u:add_bionic(BionicDataId.new('bio_remote')) "
        "u:set_max_power_level(Energy.from_kilojoule(100)) "
        "u:set_power_level(Energy.from_kilojoule(100)) "
        "out(u:has_bionic(BionicDataId.new('bio_remote')), "
        "u:has_active_bionic(BionicDataId.new('bio_remote')))")
    assert prepared == ["true,false"], prepared
    open_action_menu(game, "Misc", "View/Activate Bionics")
    game.wait_for("Remote Controller")
    game.keys("Enter", delay=1.0)  # The only bionic is on the cursor.
    game.wait_for("Perform which function:")
    game.keys("Enter", delay=1.0)  # "Control vehicle"
    game.wait_for("What to do with remote vehicle control:")
    game.keys("Enter", delay=1.0)  # "Take control of a vehicle."
    game.wait_for("Select vehicle to access")
    game.keys("Enter", delay=1.0)  # The only vehicle: Bubble Car.
    # The bionics screen hides the message log, so close it before reading the message.
    game.keys("Escape", delay=0.8)
    game.wait_for("You take control of the vehicle.")
    settle(game)


def test_remote_vehicle_controls_menu(_game):
    game = remote_vehicle_game("bn-e2e-remote-vehicle")
    try:
        enter_remote_control(game)
        assert not game.dismiss_error_popup(), "remote control setup raised a debug popup"
        open_action_menu(game, "Misc", "Control Vehicle")
        assert not game.dismiss_error_popup(), "vehicle controls on a remote vehicle raised a debug popup"
        screen = game.screen()
        assert "Vehicle controls" in screen, screen
        assert "Stop controlling" in screen or "Stop driving" in screen, screen
        game.keys("Escape", delay=1.0)
        settle(game)
        assert "wasd move" in game.screen() or "X,Y,Z" in game.screen(), game.screen()
    finally:
        game.close()


TESTS = [test_remote_vehicle_controls_menu]

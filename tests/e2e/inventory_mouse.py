"""Modern scheme mouse support in inventory menus: click a row to pick it, right click for item actions."""
import re

from helpers import arena, empty_inventory, give, spawn


def display_name(g, item):
    out = g.lua(f"local it=gapi.create_item(ItypeId.new('{item}'),-1) out(it:display_name(1))")
    assert len(out) == 1, out
    return re.sub(r"</?color[^>]*>", "", out[0])


def row_of(g, name):
    for y, line in enumerate(g.screen().splitlines()):
        if name in line:
            return line.index(name), y
    raise AssertionError(f"no row for {name!r}\n{g.screen()}")


def wielded(g):
    return g.lua("local a=gapi.get_avatar() local w={} for _,it in ipairs(a:all_items(false)) do "
                 "if a:is_wielding(it) then w[#w+1]=it:get_type():str() end end out(table.concat(w,','))")


def fresh_inventory(g):
    arena(g)
    empty_inventory(g)
    arena(g)
    give(g, "rock")
    give(g, "pipe")


def test_click_picks_an_inventory_row(g):
    fresh_inventory(g)
    pipe = display_name(g, "pipe")
    g.keys("h", delay=1.5)
    assert "Wield item" in g.screen(), "h should open the wield picker\n" + g.screen()
    x, y = row_of(g, pipe)
    g.hover(x, y)
    g.click(x, y)
    assert "Wield item" not in g.screen(), "a left click should pick the row\n" + g.screen()
    assert wielded(g) == ["pipe"], wielded(g)
    g.lua("gapi.get_avatar():drop_all_items() out('ok')")
    arena(g)


def test_right_click_opens_item_actions(g):
    fresh_inventory(g)
    rock = display_name(g, "rock")
    g.keys("i", delay=1.5)
    x, y = row_of(g, rock)
    g.click(x, y, button=2)
    screen = g.screen()
    assert "Drop" in screen and "Wield" in screen, "a right click should open the item's actions\n" + screen
    g.keys("h", delay=1)
    assert wielded(g) == ["rock"], "h must wield here, not navigate or open the guide"
    g.lua("gapi.get_avatar():drop_all_items() out('ok')")
    arena(g)


def test_click_picks_nearby_item_without_inventory(g):
    fresh_inventory(g)
    g.lua("gapi.get_avatar():drop_all_items() out('ok')")
    arena(g)
    spawn(g, 0, 0, "pipe")
    spawn(g, 1, 0, "rock")
    pipe = display_name(g, "pipe")
    g.keys("h", delay=1)
    x, y = row_of(g, pipe)
    g.click(x, y)
    assert wielded(g) == ["pipe"], "a hidden inventory column must not shift mouse selection"
    g.lua("gapi.get_avatar():drop_all_items() out('ok')")
    arena(g)


def test_wheel_moves_inventory_selection(g):
    fresh_inventory(g)
    pipe = display_name(g, "pipe")
    g.keys("h", delay=1)
    x, y = row_of(g, pipe)
    g.hover(x, y)
    # A wheel notch emits a press only, not a button-release packet.
    g.type(f"\x1b[<65;{x + 1};{y + 1}M", delay=1)
    g.keys("Enter", delay=1)
    assert wielded(g) == ["rock"], "the wheel must move the selection before Enter"
    g.lua("gapi.get_avatar():drop_all_items() out('ok')")
    arena(g)


def test_inventory_wield_and_wear_match_map_keys(g):
    fresh_inventory(g)
    pipe = display_name(g, "pipe")
    give(g, "tshirt")
    shirt = display_name(g, "tshirt")
    g.keys("i", delay=1)
    g.hover(*row_of(g, pipe))
    g.keys("h", delay=1)
    assert wielded(g) == ["pipe"], "h in inventory must wield, not move left"
    g.keys("i", delay=1)
    g.hover(*row_of(g, shirt))
    g.keys("W", delay=1)
    assert g.lua("local a=gapi.get_avatar() local worn=false for _,it in ipairs(a:all_items(false)) do "
                 "if it:get_type():str()=='tshirt' then worn=a:is_wearing(it) end end out(worn)") == ["true"]
    g.lua("gapi.get_avatar():drop_all_items() out('ok')")
    arena(g)


def test_right_click_outside_inventory_cancels(g):
    fresh_inventory(g)
    g.keys("h", delay=1)
    assert "Wield item" in g.screen(), g.screen()
    g.click(0, 0, button=2)
    assert "Wield item" not in g.screen(), g.screen()
    assert wielded(g) == [""]
    empty_inventory(g)
    arena(g)


TESTS = [test_click_picks_an_inventory_row, test_right_click_opens_item_actions,
         test_click_picks_nearby_item_without_inventory, test_wheel_moves_inventory_selection,
         test_inventory_wield_and_wear_match_map_keys, test_right_click_outside_inventory_cancels]

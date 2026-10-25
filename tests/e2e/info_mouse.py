"""Modern scheme mouse support in information menus: clickable scrollbars, rows and labels.

Covers the message log, the nearby item list, the mutations menu and the bionics tabs.
The dialogs run through their real production refresh paths and receive real pointer
clicks through tmux.
"""

from helpers import action_menu, arena, empty_inventory, settle

# The message log centers an 80x25 window on the 140x45 test terminal. The window starts
# at row 10; row 11 is its first text line, and the scrollbar runs down its left border.
MSG_X = 30
MSG_TOP = 11
BAR_X = MSG_X  # the scrollbar replaces the window's left border column
UP_ARROW_Y = 11
DOWN_ARROW_Y = 33

SPAWN_ITEMS = ["rock", "pipe", "hammer", "screwdriver", "nail", "stick", "2x4", "splinter",
               "crowbar", "flashlight", "rag", "string_36", "battery", "lighter", "bandages",
               "aspirin", "bottle_glass", "tshirt", "jeans", "sneakers", "socks", "duct_tape",
               "wrench", "hacksaw"]

DEBUG_MUTATIONS = ["DEBUG_BIONICS", "DEBUG_CLOAK", "DEBUG_HS", "DEBUG_HT", "DEBUG_LS",
                   "DEBUG_NIGHTVISION", "DEBUG_NOCLIP", "DEBUG_NODMG", "DEBUG_NOSCENT",
                   "DEBUG_NOTEMP", "DEBUG_SILENT", "DEBUG_STAMINA", "DEBUG_STORAGE",
                   "DEBUG_WEIGHTLESSNESS"]


def lines(g):
    return g.screen().splitlines()


def msg_top_line(g):
    return lines(g)[MSG_TOP][MSG_X:].strip()


def open_messages(g):
    arena(g)
    assert g.lua("for i=1,40 do gapi.add_msg('scroll marker '..i) end out('ok')") == ["ok"]
    settle(g)
    g.keys("P", delay=1.5)
    assert "to filter" in g.screen(), g.screen()


def test_message_scrollbar_track_and_arrows(g):
    open_messages(g)
    top0 = msg_top_line(g)
    assert top0, g.screen()
    # A track click near the top jumps the view towards the oldest messages.
    g.click(BAR_X, MSG_TOP + 2)
    top1 = msg_top_line(g)
    assert top1 != top0, "track click must scroll\n" + g.screen()
    # The up arrow at the very top cannot scroll past the first message.
    g.click(BAR_X, UP_ARROW_Y)
    assert msg_top_line(g) == top1, "up arrow at the top must hold still\n" + g.screen()
    # The down arrow moves the view by exactly one row.
    g.click(BAR_X, DOWN_ARROW_Y)
    top2 = msg_top_line(g)
    assert top2 != top1, "down arrow must scroll\n" + g.screen()
    g.click(BAR_X, UP_ARROW_Y)
    assert msg_top_line(g) == top1, "up arrow must undo one row\n" + g.screen()
    g.keys("Escape", delay=1)


def test_message_wheel_scrolls(g):
    open_messages(g)
    top0 = msg_top_line(g)
    g.click(BAR_X, MSG_TOP + 2)
    top1 = msg_top_line(g)
    assert top1 != top0, "track click must scroll\n" + g.screen()
    # A wheel notch moves the text three lines.
    g.type(f"\x1b[<65;{MSG_X + 11};{MSG_TOP + 5}M", delay=1)
    assert msg_top_line(g) != top1, "wheel down must scroll the log\n" + g.screen()
    g.keys("Escape", delay=1)


def open_item_list(g):
    arena(g)
    had_nightvision = g.lua("out(gapi.get_avatar():has_trait("
                           "MutationBranchId.new('DEBUG_NIGHTVISION')))") == ["true"]
    assert g.lua("gapi.get_avatar():set_mutation(MutationBranchId.new('DEBUG_NIGHTVISION')) "
                 "local p=here(0,0) local size=M:get_map_size() "
                 "for x=0,size-1 do for y=0,size-1 do "
                 "M:clear_items_at(TripointBubMs.new(x,y,p.z)) end end out('ok')") == ["ok"]
    for i, item in enumerate(SPAWN_ITEMS):
        spawn_x = i % 4 - 1
        spawn_y = i // 4 - 2
        if i == len(SPAWN_ITEMS) - 1:
            spawn_x, spawn_y = 4, 0
        assert g.lua(f"local p=here({spawn_x},{spawn_y}) "
                     f"M:create_item_at(p, ItypeId.new('{item}'), -1) out('ok')") == ["ok"], item
    action_menu(g, "Look", "List all items around the player")
    assert "Items" in g.screen(), g.screen()
    return had_nightvision


def item_list_info_row(g):
    """Row index of the item info pane title on the 45 row test terminal."""
    rows = lines(g)
    info_y = len(rows) - 22
    assert "< " in rows[info_y] and " >" in rows[info_y], g.screen()
    return info_y


def item_list_bar_x(g):
    rows = lines(g)
    return rows[0].index("<Tab> ") - 2  # the list window's left border column


def close_item_list(g, had_nightvision):
    g.keys("Escape", delay=1)
    if not had_nightvision:
        assert g.lua("gapi.get_avatar():unset_mutation("
                     "MutationBranchId.new('DEBUG_NIGHTVISION')) out('ok')") == ["ok"]
    arena(g)


def test_item_list_row_click_selects(g):
    had_nightvision = open_item_list(g)
    target = next((y, l) for y, l in enumerate(lines(g)) if "hammer" in l and y < 20)
    g.click(target[1].index("hammer"), target[0])
    title = lines(g)[item_list_info_row(g)]
    assert "hammer" in title, "clicking a row must select it in the info pane\n" + g.screen()
    close_item_list(g, had_nightvision)


def test_item_list_scrollbar_track_jumps_to_last_row(g):
    had_nightvision = open_item_list(g)
    info_y = item_list_info_row(g)
    g.click(item_list_bar_x(g), 20)
    title = lines(g)[info_y]
    assert "hacksaw" in title, f"track click must select the last item\n{g.screen()}"
    bottom_row = lines(g)[info_y - 2]
    assert "hacksaw" in bottom_row, f"the selected item must be the last visible row\n{g.screen()}"
    close_item_list(g, had_nightvision)


def set_debug_mutations(g):
    empty_inventory(g)
    ids = ", ".join(f"'{m}'" for m in DEBUG_MUTATIONS)
    assert g.lua(f"local a=gapi.get_avatar() for _,id in ipairs({{{ids}}}) do "
                 "a:set_mutation(MutationBranchId.new(id)) end out('ok')") == ["ok"]


def mutation_row(g, name):
    return next((y, l) for y, l in enumerate(lines(g)) if name in l)


def test_mutation_row_click_shows_description(g):
    set_debug_mutations(g)
    arena(g)
    action_menu(g, "Misc", "View/Activate Mutations")
    assert "Passive:" in g.screen(), g.screen()
    g.keys("!", delay=1)  # switch to examining so clicked rows draw their description
    y, line = mutation_row(g, "Debug Life Support")
    g.click(line.index("Debug Life Support"), y)
    assert "debug all year long" in g.screen(), \
        "clicking a mutation row in examining mode must show its description\n" + g.screen()
    g.keys("Escape", delay=1)
    empty_inventory(g)
    arena(g)


def test_mutation_second_click_keeps_activation_prompt(g):
    set_debug_mutations(g)
    arena(g)
    action_menu(g, "Misc", "View/Activate Mutations")
    y, line = mutation_row(g, "Debug Life Support")
    x = line.index("Debug Life Support")
    g.click(x, y)  # first click selects only
    assert "You cannot activate" not in g.screen(), g.screen()
    g.click(x, y)  # second click on the same row runs the row's Enter action
    assert "You cannot activate" in g.screen(), \
        "the second click must keep the activation prompt\n" + g.screen()
    g.keys("Escape", delay=1)
    g.keys("Escape", delay=1)
    empty_inventory(g)
    arena(g)


def test_bionic_tab_click_switches_list(g):
    empty_inventory(g)
    assert g.lua("local a=gapi.get_avatar() "
                 "a:add_bionic(BionicDataId.new('bio_night_vision')) "
                 "a:add_bionic(BionicDataId.new('bio_power_storage')) out('ok')") == ["ok"]
    arena(g)
    action_menu(g, "Misc", "View/Activate Bionics")
    assert "ACTIVE (" in g.screen(), g.screen()
    assert "Power Storage" not in g.screen(), g.screen()  # passive list is hidden
    rows = lines(g)
    tab_y = next(y for y, l in enumerate(rows) if "PASSIVE (" in l)
    g.click(rows[tab_y].index("PASSIVE ("), tab_y)
    assert "Power Storage" in g.screen(), \
        "clicking the passive tab must show the passive list\n" + g.screen()
    assert "Night Vision" not in g.screen(), g.screen()
    g.keys("Escape", delay=1)
    empty_inventory(g)
    arena(g)


TESTS = [test_message_scrollbar_track_and_arrows, test_message_wheel_scrolls,
         test_item_list_row_click_selects, test_item_list_scrollbar_track_jumps_to_last_row,
         test_mutation_row_click_shows_description, test_mutation_second_click_keeps_activation_prompt,
         test_bionic_tab_click_switches_list]

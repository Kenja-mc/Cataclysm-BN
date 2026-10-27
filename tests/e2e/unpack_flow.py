"""Unpacking opens one take list; counts, marking and the option match what is moved."""
from fixtures import shared_game
from helpers import (HELPERS, arena, count_at, count_carried, empty_inventory, give,
                     wait_until)
from inventory_mouse import row_of


def activate_kit(g, filter_text, item_text, key="v", title="Use which item?"):
    g.keys(key, delay=0.5)
    g.wait_for(title)
    g.keys("/", delay=0.3)
    g.type(filter_text)
    # The first Enter applies the filter; a second one picks the highlighted kit.
    g.keys("Enter", delay=0.6)
    g.wait_for(item_text)
    g.settle_screen(minimum=0.3, timeout=2.0)
    g.keys("Enter", delay=1.0)


def open_unpack(g, filter_text, item_text):
    activate_kit(g, filter_text, item_text)
    g.wait_for("ITEMS TO TAKE", timeout=10)


def filter_take_list(g, text):
    g.keys("/", delay=0.3)
    g.keys("C-u", delay=0.2)  # clear a filter left by an earlier phase
    g.type(text)
    g.keys("Enter", delay=0.6)
    g.keys("Down", delay=0.3)  # the only matching row


def prepare_kit(g, kit):
    arena(g)
    empty_inventory(g)
    arena(g)
    give(g, kit)


def worn_count(g, item):
    return int(g.lua(f"local a=gapi.get_avatar() local n=0 "
                     f"for _,it in ipairs(a:all_items(false)) do "
                     f"if a:is_wearing(it) and it:get_type():str()=='{item}' then n=n+1 end end "
                     f"out(n)")[0])


def test_first_aid_kit_opens_one_take_list(g):
    prepare_kit(g, "1st_aid")
    open_unpack(g, "compact first aid", "compact first aid kit")
    screen = g.screen()
    for name in ("medical tape", "bandage", "Instruction Booklet"):
        assert name in screen, f"{name} must be in the one take list:\n{screen}"

    g.keys("Enter", delay=1)
    assert wait_until(lambda: count_carried(g, "1st_aid") == 0), g.screen()
    assert wait_until(lambda: count_carried(g, "medical_tape") > 0), g.screen()
    assert wait_until(lambda: count_carried(g, "bandages") > 0), g.screen()
    assert count_at(g, 0, 0, "medical_tape") == 0, "confirmed contents must be carried"

    empty_inventory(g)
    arena(g)


def test_stacked_contents_are_taken_whole(g):
    prepare_kit(g, "1st_aid")
    open_unpack(g, "compact first aid", "compact first aid kit")
    screen = g.screen()
    assert "of 6" not in screen, "a fully marked stack must not promise a partial amount:\n" + screen

    g.keys("Enter", delay=1)

    assert wait_until(lambda: count_carried(g, "bandages") == 6), g.screen()
    assert count_at(g, 0, 0, "bandages") == 0, "every displayed charge must move"

    empty_inventory(g)
    arena(g)


def test_unchecked_first_aid_contents_stay_on_the_floor(g):
    prepare_kit(g, "1st_aid")
    open_unpack(g, "compact first aid", "compact first aid kit")
    x, y = row_of(g, "bandage")
    g.click(x, y)
    g.keys("Enter", delay=1)

    assert wait_until(lambda: count_at(g, 0, 0, "bandages") == 6), g.screen()
    assert count_carried(g, "bandages") == 0, "the unchecked stack must stay on the floor"
    assert wait_until(lambda: count_carried(g, "medical_tape") > 0), g.screen()
    assert wait_until(lambda: "You leave" in g.screen(), 10), g.screen()
    assert "bandage" in g.screen(), "the leave message must name the unchecked item"

    empty_inventory(g)
    arena(g)


def test_right_marks_only_the_highlighted_row(g):
    prepare_kit(g, "1st_aid")
    open_unpack(g, "compact first aid", "compact first aid kit")
    # Filter to one identifiable item, so the cursor choice does not depend on list ordering.
    filter_take_list(g, "bandage")
    g.keys("Right", delay=0.5)
    g.keys("Enter", delay=1)

    assert wait_until(lambda: count_at(g, 0, 0, "bandages") == 6), g.screen()
    assert count_carried(g, "bandages") == 0, "Right must affect only the highlighted row"
    # The filter hid these rows; Right must not have unmarked them.
    for hidden in ("medical_tape", "medical_gauze", "booklet_firstaid"):
        assert wait_until(lambda item=hidden: count_carried(g, item) > 0), g.screen()

    empty_inventory(g)
    arena(g)


def test_typed_count_takes_part_of_a_stack(g):
    prepare_kit(g, "1st_aid")
    open_unpack(g, "compact first aid", "compact first aid kit")
    x, y = row_of(g, "bandage")
    g.keys("3", delay=0.3)
    g.click(x, y)
    g.keys("Enter", delay=1)

    assert wait_until(lambda: count_carried(g, "bandages") == 3), g.screen()
    assert wait_until(lambda: count_at(g, 0, 0, "bandages") == 3), g.screen()

    empty_inventory(g)
    arena(g)


def test_full_inventory_leaves_what_does_not_fit(g):
    arena(g)
    empty_inventory(g)
    arena(g)
    # A 500 ml jacket caps volume, so the 1 L kit's contents cannot all be carried.
    assert g.lua("local a=gapi.get_avatar() a:clear_mutations() "
                 "local h=a:create_item(ItypeId.new('jacket_evac'),-1) assert(a:wear(h,false)) "
                 "out('ok')") == ["ok"]
    give(g, "1st_aid")
    open_unpack(g, "compact first aid", "compact first aid kit")
    g.keys("Enter", delay=1)

    assert wait_until(lambda: count_at(g, 0, 0, "bandages") > 0), g.screen()
    assert wait_until(lambda: count_carried(g, "medical_tape") > 0), g.screen()
    assert wait_until(lambda: "cannot carry" in g.screen(), 10), g.screen()
    assert wait_until(lambda: "You leave" in g.screen(), 10), g.screen()
    assert "bandage" in g.screen(), "the leave message must name what did not fit"

    empty_inventory(g)
    arena(g)


def test_wearing_from_the_list_prompts_when_the_slot_is_filled(g):
    arena(g)
    empty_inventory(g)
    arena(g)
    assert g.lua("local a=gapi.get_avatar() "
                 "local h=a:create_item(ItypeId.new('gloves_medical'),-1) assert(a:wear(h,false)) "
                 "local m=a:create_item(ItypeId.new('mask_dust'),-1) assert(a:wear(m,false)) "
                 "out('ok')") == ["ok"]
    give(g, "1st_aid_deluxe")
    open_unpack(g, "aid kit", "first aid kit")

    # Drive both dialogs without Lua reads: a read closes the open menu.
    filter_take_list(g, "medical gloves")
    g.keys("W", delay=1.0)
    g.wait_for("You are already wearing")
    for option in ("Replace it", "Layer it", "Cancel"):
        assert option in g.screen(), f"the occupied-slot dialog must offer {option}:\n{g.screen()}"
    g.keys("l", delay=1.0)

    filter_take_list(g, "dust mask")
    g.keys("W", delay=1.0)
    g.wait_for("You are already wearing")
    for option in ("Replace it", "Layer it", "Cancel"):
        assert option in g.screen(), f"the occupied-slot dialog must offer {option}:\n{g.screen()}"
    g.keys("r", delay=1.0)

    g.keys("Enter", delay=1.0)
    assert wait_until(lambda: "ITEMS TO TAKE" not in g.screen(), 10), g.screen()

    assert worn_count(g, "gloves_medical") == 2, "Layer must add the second pair"
    assert worn_count(g, "mask_dust") == 1, "Replace must not layer a second mask"
    assert count_carried(g, "mask_dust") == 2, "the replaced mask must be stowed, not lost"
    assert count_carried(g, "1st_aid") == 0, "the kit is still consumed"

    empty_inventory(g)
    arena(g)


def test_cancel_carries_nothing(g):
    prepare_kit(g, "1st_aid")
    open_unpack(g, "compact first aid", "compact first aid kit")
    g.keys("Escape", delay=1)
    assert wait_until(lambda: "ITEMS TO TAKE" not in g.screen(), 10), g.screen()

    assert count_carried(g, "medical_tape") == 0, "cancel must not carry anything"
    assert wait_until(lambda: count_at(g, 0, 0, "medical_tape") > 0), g.screen()
    assert count_carried(g, "1st_aid") == 0, "the kit is still consumed"

    empty_inventory(g)
    arena(g)


def test_classic_list_uses_keyboard_wording(_g):
    with shared_game("bn-e2e-unpack-classic", define=HELPERS,
                     options={"CONTROL_SCHEME": "classic", "SAFEMODE": "false"}) as game:
        prepare_kit(game, "1st_aid")
        activate_kit(game, "compact first aid", "compact first aid kit", key="a", title="Use item")
        game.wait_for("ITEMS TO TAKE", timeout=10)
        hint = next(line for line in game.screen().splitlines() if "mark one" in line)
        assert "Click" not in hint, "Classic has no mouse routing:\n" + hint
        assert "Press" in hint, "the hint must name the mark key:\n" + hint

        game.keys("Enter", delay=1)
        assert wait_until(lambda: count_carried(game, "medical_tape") > 0), game.screen()
        assert count_carried(game, "1st_aid") == 0

        empty_inventory(game)
        arena(game)


def test_option_drops_everything_without_a_list(_g):
    with shared_game("bn-e2e-unpack-option", define=HELPERS,
                     options={"UNPACK_TAKE_LIST": "false", "SAFEMODE": "false"}) as game:
        prepare_kit(game, "1st_aid")
        activate_kit(game, "compact first aid", "compact first aid kit")
        assert wait_until(lambda: count_at(game, 0, 0, "bandages") == 6), game.screen()
        assert "ITEMS TO TAKE" not in game.screen(), "the option must skip the take list"
        assert count_carried(game, "medical_tape") == 0, "the old flow carries nothing"
        assert wait_until(lambda: "You leave" in game.screen(), 10), game.screen()

        empty_inventory(game)
        arena(game)


TESTS = [test_first_aid_kit_opens_one_take_list, test_stacked_contents_are_taken_whole,
         test_unchecked_first_aid_contents_stay_on_the_floor,
         test_right_marks_only_the_highlighted_row, test_typed_count_takes_part_of_a_stack,
         test_full_inventory_leaves_what_does_not_fit,
         test_wearing_from_the_list_prompts_when_the_slot_is_filled, test_cancel_carries_nothing,
         test_classic_list_uses_keyboard_wording, test_option_drops_everything_without_a_list]

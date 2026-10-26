"""Unpacking opens one take list, and unchecked contents stay on the floor."""
from helpers import arena, count_at, count_carried, empty_inventory, give, wait_until
from inventory_mouse import row_of


def open_unpack(g, filter_text, item_text):
    g.keys("v", delay=0.5)
    g.wait_for("Use which item?")
    g.keys("/", delay=0.3)
    g.type(filter_text)
    # The first Enter applies the filter; a second one picks the highlighted kit.
    g.keys("Enter", delay=0.6)
    g.wait_for(item_text)
    g.settle_screen(minimum=0.3, timeout=2.0)
    g.keys("Enter", delay=1.0)
    g.wait_for("ITEMS TO TAKE", timeout=10)


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
    assert "You unpack the compact first aid kit." in g.screen(), g.screen()
    assert wait_until(lambda: count_carried(g, "1st_aid") == 0), g.screen()
    assert count_carried(g, "medical_tape") > 0, g.screen()
    assert count_carried(g, "bandages") > 0, g.screen()
    assert count_at(g, 0, 0, "medical_tape") == 0, "confirmed contents must be carried"
    assert "You take" in g.screen(), g.screen()


def test_unchecked_first_aid_contents_stay_on_the_floor(g):
    prepare_kit(g, "1st_aid")
    open_unpack(g, "compact first aid", "compact first aid kit")
    x, y = row_of(g, "bandage")
    g.click(x, y)
    assert "1 of 6 bandages" not in g.screen(), "a click must uncheck the row:\n" + g.screen()
    g.keys("Enter", delay=1)

    assert wait_until(lambda: count_at(g, 0, 0, "bandages") > 0), g.screen()
    assert count_carried(g, "bandages") == 0, "the unchecked stack must stay on the floor"
    assert count_carried(g, "medical_tape") > 0, "the checked contents must still be carried"
    assert wait_until(lambda: "You leave" in g.screen(), 10), g.screen()
    assert "bandage" in g.screen(), "the leave message must name the unchecked item"


def test_full_inventory_leaves_what_does_not_fit(g):
    arena(g)
    empty_inventory(g)
    arena(g)
    # A 500 ml jacket caps volume, so the 1 L kit's contents cannot all be carried.
    assert g.lua("local a=gapi.get_avatar() a:clear_mutations() "
                 "local h=a:create_item(ItypeId.new('jacket_evac'),1) assert(a:wear(h,false)) "
                 "out('ok')") == ["ok"]
    give(g, "1st_aid")
    open_unpack(g, "compact first aid", "compact first aid kit")
    g.keys("Enter", delay=1)

    assert wait_until(lambda: count_at(g, 0, 0, "bandages") > 0), g.screen()
    assert count_carried(g, "medical_tape") > 0, "the contents that fit must still be taken"
    assert wait_until(lambda: "You leave" in g.screen(), 10), g.screen()
    assert "bandage" in g.screen(), "the leave message must name what did not fit"

    empty_inventory(g)
    arena(g)


def test_wearing_from_the_list_prompts_when_the_slot_is_filled(g):
    arena(g)
    empty_inventory(g)
    arena(g)
    assert g.lua("local a=gapi.get_avatar() "
                 "local h=a:create_item(ItypeId.new('gloves_medical'),1) assert(a:wear(h,false)) "
                 "out('ok')") == ["ok"]
    give(g, "1st_aid_deluxe")
    open_unpack(g, "aid kit", "first aid kit")
    # The list starts on the scissors; the medical gloves are two rows below.
    g.keys("Down", "Down", delay=0.3)
    g.keys("W", delay=1.0)
    g.wait_for("You are already wearing")
    screen = g.screen()
    for option in ("Replace it", "Layer it", "Cancel"):
        assert option in screen, f"the occupied-slot dialog must offer {option}:\n{screen}"
    assert "encumbrance" in screen, "the dialog must show the layering cost:\n" + screen

    g.keys("l", delay=1.0)
    assert wait_until(lambda: worn_count(g, "gloves_medical") == 2), g.screen()
    g.keys("Escape", delay=0.8)
    assert wait_until(lambda: "ITEMS TO TAKE" not in g.screen(), 10), g.screen()

    empty_inventory(g)
    arena(g)


def test_cancel_carries_nothing(g):
    prepare_kit(g, "1st_aid")
    open_unpack(g, "compact first aid", "compact first aid kit")
    g.keys("Escape", delay=1)
    assert wait_until(lambda: "ITEMS TO TAKE" not in g.screen(), 10), g.screen()

    assert count_carried(g, "medical_tape") == 0, "cancel must not carry anything"
    assert "You take" not in g.screen(), "cancel must not report taken items"
    assert wait_until(lambda: count_at(g, 0, 0, "medical_tape") > 0), g.screen()
    assert count_carried(g, "1st_aid") == 0, "the kit is still consumed"

    empty_inventory(g)
    arena(g)


TESTS = [test_first_aid_kit_opens_one_take_list, test_unchecked_first_aid_contents_stay_on_the_floor,
         test_full_inventory_leaves_what_does_not_fit, test_wearing_from_the_list_prompts_when_the_slot_is_filled,
         test_cancel_carries_nothing]

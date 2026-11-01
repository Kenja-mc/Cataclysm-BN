# Visual changes

Screens captured from the terminal build (132×42, Tokyo Night palette) by
`tests/e2e`'s tmux harness, so they show the real game, not mock-ups. These earlier captures predate
the grouped right sidebar and can show obsolete controls. Use `OVERHAUL.md` for current behavior
and `CHANGELOG-OVERHAUL.md` for changes by date.

## Title screen

The main-menu wordmark keeps the Bright Nights logo and adds a text-only **OVERHAUL** mark
beneath it. The title art fits an 80-column terminal and uses the same asset in curses and tiles.

## In game

New configurations use the **grouped** sidebar, based on the Opus HUD proposal. Its HUD readings
now float over the map as ten titled windows, and the remaining panels (Location, Controls, Map and
so on) stay on the right. The **labels** and **labels-narrow** layouts use the same windows. The
Classic and compact layouts keep their combined panels unchanged.

### Floating HUD windows

The slide-2 mockup's minimizable windows are the default HUD layout, and no keybinding was added
for them.

- The **Weather**, **Combat**, **Needs**, **Limbs**, **Stats**, **Movement**, **Weight**,
  **Compass**, **Log** and **Vehicle** windows each have a title row with the window name, one line
  of live state and `[-]` at the right. Clicking `[-]` collapses the window to that row — the
  control becomes `[+]` and the live state stays, so the readings are hidden, not lost. Clicking
  the window name (or `[+]`) restores it.
- Click a title to pick the window up, move the pointer, then click again to put it down. The
  rest of a collapsed window's title row is still a drag handle, so it can be moved without
  expanding. The window stays inside the map area and never covers the sidebar column.
- Left and right clicks on a window never reach the map, so a stray click cannot walk, aim or
  open a tile action under the window.
- Position, collapsed state and visibility are saved per character.
- **Enter → Misc → Sidebar Options** lists the windows in the third column, below the layouts.
  Move there with the arrow keys and press Tab to enable or disable the selected window; a mouse is
  never required. Disabling a window puts its readings back in the sidebar. A window that cannot
  fit the map — a small terminal with several windows open — also hands its reading back instead
  of overlapping another.
- The readings mirror the sidebar panels: **Limbs** gives each limb's health bar and worst wound;
  **Stats** gives Str, Dex, Int, Per in the panel's boosted/reduced colours, bionic power and the
  safe-mode readout; **Movement** gives speed, move cost, sound, stamina, mood and focus; **Weight**
  gives carried weight and volume; **Compass** gives each direction's seen symbols, counts and
  threat colour; **Log** gives the recent coloured message lines at the window's width; **Vehicle**
  gives speed, azimuth, engine, fuel and battery. The **Needs** window lists only needs that call
  for attention, with a glyph and label instead of an adjective, or a **Needs met** row. The
  **Vehicle** window exists only while aboard or remote-controlling a vehicle.
- Both the terminal and tiles builds draw the same windows. Where a build has no mouse, only the
  Sidebar Options path applies.
- **Options → Interface → Floating HUD windows** is on by default for the modern layouts. Turning
  it off keeps the old fixed corner boxes; the weather, status and vehicle box corner options still
  seed each window's first position and visibility. **Compact corner bars** also keeps the old
  layout, and Classic and compact layouts always keep their combined panels.
- The vehicle reading is a replaceable provider
  (`hud_windows::set_vehicle_provider`) so the driving-dashboard work can take that window over
  without changing its id, placement, collapse or save state.
- Clicking or dragging a window brings it to the front, and **Enter** on its row in Sidebar
  Options does the same from the keyboard. The stacking order saves per character with the
  positions. A dragged window keeps its top-left through a collapse; an untouched default window
  stays bottom-anchored in its corner.

![Earlier in-game capture: weather and weapon boxes, body panel, and obsolete Controls-strip shortcuts](images/game.png)


- Top left: the **weather box** (icon, weather, time) and the **Status box** (weapon, style, stance
  and needs; this capture shows its earlier weapon-only form).
- Sidebar: the **body panel** (a figure coloured by limb health, wounds beside it) and the
  **Controls strip** (the capture predates compact action families; current hints use live bindings).
- Map: **readable glyphs**. Trees are ♣, pines ♠ and saplings τ instead of 7, 4 and 1.
- Rounded window corners.
- **Compact corner bars** (Options → Interface) replaces the two boxes with one-row strips:
  `Weather: Drizzle  │  Spring 16 morning  │  Light: bright  │  Wind: Calm Air NE`. The status
  strip carries the weapon, style and stance. The sidebar keeps its panels either way.

For comparison, the same kind of start with the classic control scheme, classic colours, digit
glyphs and the map boxes turned off. The fork's sidebar panels stay; each can be hidden from the
sidebar options.

![Classic controls and colours: vi-keys in the Controls strip, trees drawn as 7, 4 and 1](images/classic_game.png)

## Mouse tile selection

![Obsolete Modern click-to-walk hint: an earlier Mouse View capture](images/hover.png)

Modern uses keyboard-only movement. Hovering inspects a tile; right click selects it freely,
and left click uses an adjacent door, item or furniture, or attacks the clicked hostile.
Space offers actions for the selected tile, including explicit Jump and Smash choices.
With nothing selected, Space lists nearby actions and highlights their tiles. Classic retains upstream mouse movement.

Tile hit-testing follows the display scaling factor and the sidebar position, so moving the
sidebar left or choosing 2x scaling does not shift the tile under the pointer. Menu clicks use
the text grid, even when the terrain tileset is isometric.

## Body panel and details

![Body panel listing a bleeding left arm and a bandaged right leg](images/body_panel.png)

![Earlier limb-details capture with obsolete H shortcut; now Enter → Info → Body status](images/body_details.png)

## First game

![Earlier welcome-card capture with obsolete keys; current controls use Enter, inventory and Space families](images/welcome.png)

![Death choice: Permadeath or Roleplay](images/death_choice.png)

The welcome card lists the core keys with their live bindings, then asks how death works, like
Caves of Qud's Classic and Roleplay modes.

## Prompts and menus

![Save and quit prompt with Yes and No buttons, No highlighted](images/yes_no.png)

Yes/No prompts are buttons that open on **No**; Enter or a click answers and Esc cancels.

![Inventory with one rings line holding different rings, and a tiara](images/inventory.png)

Jewelry is one item per form. Different rings stack on one line, and each keeps its own gem,
metal, name and price.

![Crafting menu opening on a tab full of recipes](images/crafting.png)

Open crafting with **`i`, then F5 Craft**, including with an empty inventory. The crafting menu
opens on a tab that has recipes instead of an empty one.

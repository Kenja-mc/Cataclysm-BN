# Visual changes

Screens captured from the terminal build (132×42, Tokyo Night palette) by
`tests/e2e`'s tmux harness, so they show the real game, not mock-ups. These earlier captures predate
the grouped right sidebar and can show obsolete controls. Use `OVERHAUL.md` for current behavior
and `CHANGELOG-OVERHAUL.md` for changes by date.

## Title screen

The main-menu wordmark keeps the Bright Nights logo and adds a text-only **OVERHAUL** mark
beneath it. The title art fits an 80-column terminal and uses the same asset in curses and tiles.

## In game

New configurations use the **grouped** sidebar, based on the Opus HUD proposal. Weather,
Character and Needs sit on the right instead of covering map tiles. Existing saved layouts stay
unchanged. Select grouped in **Enter → Misc → Sidebar Options** to try it.

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

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

## Driving dashboard

The floating HUD's **Vehicle** window is the one place the dashboard lives; the fixed layouts keep
the compact vehicle readout. It is type-first, like the fork's text-only HUD option, and adds no
new art:

```
Vehicle  24 mph N [-]
Speed    ###---
Cruise   On 40 mph
Heading  0°
Engine   On
gasoline ##---- 42%
battery  #----- 18% low
```

- The title row carries the speed, unit and compass letter; the body carries the speed bar,
  azimuth, cruise state and target, engine state, both tanks and the aircraft row. No reading is
  printed twice, which keeps the title-driven window narrow.
- One label column, a six-cell bar and one short value give a 24-cell window with **Text only**,
  26 with Unicode icons and 27 with the bundled icon font; at 80×25 that leaves 9–12 of the 36 map
  columns. A `WING` vehicle adds a takeoff row and three cells. The heading, fuel and battery rows
  use the existing compass, fuel and battery icons; **Text only** drops the icon column and leaves
  the labels.
- Palette: the speed row uses the compact readout's strain colours, the engine row uses green,
  yellow and red for strain, fuel is grey/yellow/red, battery is cyan/yellow/red, cruise-on is
  green, `lift` is green and `no lift` is red, and remote control is cyan.
- Every colour has a text or shape cue: `On`/`Off`, `low`/`empty`, `!`/`!!`/`!!!` strain marks, a
  bar of `#` and `-`, `lift`/`no lift`, and a signed speed for reverse. A monochrome terminal keeps
  all of the information. The speed bar fills toward the safe speed; above it the row first turns
  yellow and gains a marker.
- `Remote control` appears only while a remote vehicle is under control. The aircraft row keeps
  the takeoff speed in the configured unit and reports whether the current speed reaches it; a wing
  that cannot lift reports `no lift`.
- No new images, sprites or glyph art are added: the icons come from the fork's existing HUD set.
  There is no copied Zomboid asset and no generated artwork. Project Zomboid is a layout
  reference only.

The terminal tests drive, drain a tank to `low` and `empty`, reach takeoff speed, take remote
control, use km/h and Unicode icons, and check the window bounds at 80×25. `tests/e2e/hud_tiles.py`
hides the other floating windows in its fixture, then clicks the vehicle window's collapse control
at 80×25 at both 1x and 2x scaling and checks the dashboard's exact cell footprint on the map.

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

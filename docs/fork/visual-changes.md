# Visual changes

Screens captured from the terminal build (132×42, Tokyo Night palette) by
`tests/e2e`'s tmux harness, so they show the real game, not mock-ups. `OVERHAUL.md` explains
each feature; `CHANGELOG-OVERHAUL.md` lists them by date.

## In game

![In game: weather and weapon boxes top left, body panel and Controls strip in the sidebar, readable trees](images/game.png)

- Top left: the **weather box** (icon, weather, time) and the **weapon box** (weapon, fighting style).
- Sidebar: the **body panel** (a figure coloured by limb health, wounds beside it) and the
  **Controls strip** with the live key for each common action.
- Map: **readable glyphs**. Trees are ♣, pines ♠ and saplings τ instead of 7, 4 and 1.
- Rounded window corners.

For comparison, the same kind of start with the classic control scheme, classic colours, digit
glyphs and the map boxes turned off. The fork's sidebar panels stay; each can be hidden from the
sidebar options.

![Classic controls and colours: vi-keys in the Controls strip, trees drawn as 7, 4 and 1](images/classic_game.png)

## Mouse tile selection

![Hovering a tile: the Mouse View box describes it and its bottom border says what a click does](images/hover.png)

Hovering a tile highlights it, previews the route and names the click action on the Mouse View
border ("click: walk here (2 steps)"). Left click does it; right click lists every option.

## Body panel and details

![Body panel listing a bleeding left arm and a bandaged right leg](images/body_panel.png)

![H opens every limb's health, its wounds and a reminder of what treats them](images/body_details.png)

## First game

![Welcome card listing the core keys and the mouse](images/welcome.png)

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

The crafting menu opens on a tab that has recipes instead of an empty one.

# Caves of Qud and Dwarf Fortress: accessibility before Steam

Research notes behind the death-mode choice, first-time tips and key names in the hover hint.
Sources were press releases, patch notes, the Qud wiki and interviews (PC Gamer 2019 and 2021 with
Tarn Adams). Neither studio published a postmortem; reasons marked "inferred" are ours.

## Caves of Qud (1.0, December 2024)

- **Game modes chosen at start**: Classic (permadeath), Roleplay (checkpoint at settlements, reload
  on death), Wander (peaceful start, XP for discovery). Inferred: permadeath was the entry barrier.
- **New UI** with mouse and keyboard, clickable screen-edge travel, gamepad and Steam Deck support.
- **Tooltips** on attributes and menus, with a configurable delay.
- **Hotbar** with auto-hotkeyed abilities; button glyphs wherever a bind is shown.
- **Autoexplore danger indicator**; held-key movement stops on danger.
- **Layout options**: docked log and minimap, hide sidebar, opacity, window lock.
- **Tutorial** with a preset character (October 2024, after beta feedback).
- **Classic UI kept** as an option.

## Dwarf Fortress (Steam, December 2022)

- **Pixel tiles** instead of ASCII.
- **Mouse menus**: "right-click your carpenter workshop, click a bed, and there's your bed" (Tarn Adams,
  2019), replacing letter-key menu layers.
- **One Look panel and tooltips** instead of information spread over many keypresses.
- **Search field** on the stockpile screen.
- **First-embark tutorial**: "We want the world to be able to lose this game" (Zach Adams).
- Zach Adams afterwards: still "one of the most torturous games to learn". UI alone does not remove
  complexity.

## What the fork took

| Idea                                  | Status in the fork                                               |
| ------------------------------------- | ---------------------------------------------------------------- |
| Choose Classic or Roleplay at start   | Welcome card asks; sets upstream's _Prompt on character death_   |
| Tutorial hints                        | One-line first-time tips, once per character, option to turn off |
| Binds shown wherever an action is     | Hover hint names the key; Controls strip already did             |
| Danger stops automation               | Already upstream: "Spotted X--safe mode is on!"                  |
| Search in long lists                  | Already upstream: `/` filters menus and inventory                |
| Hide sidebar                          | Already upstream: toggle panel admin                             |
| One Look panel                        | Not done                                                         |
| Keep the old behavior behind a toggle | Every item above is an option                                    |

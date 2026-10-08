# Novice playtest 1

Written by an AI agent role-playing a newcomer who has never played Cataclysm. It played the frozen
build at commit 4d1982a for about 250–300 inputs and roughly 8 in-game minutes, and never fought
anything.

## What it hit, and what changed

| Problem the newcomer hit | Status |
| --- | --- |
| Loading takes about 2 minutes with no progress shown | Partly fixed: migration finalization was quadratic (see the "Speed up item migrations" commit) |
| Map glyphs are hard to read (trees are `7` `4` `1`, `0` is several things) | Open: readable-glyph option proposed |
| Walking into obstacles gives no feedback | Fixed: "The tree is in the way." |
| No run or auto-explore; click-to-travel is undiscoverable | Open |
| No sense of where to go | Open |
| Crafting says "You can't do that!" without a reason | Fixed: it now points at the missing parts shown in red |
| "Dispose of pliers and wield stick" sounds destructive | Fixed: "Put away pliers and wield stick" |
| Help movement page runs key names together | Fixed: each tag shows one key, with separators |
| Tutorial teaches vi-keys | Fixed: tutorial text uses live key placeholders, so it matches either scheme |
| Shift+S asks to save and quit | Kept: it already asks for confirmation |
| Strange default start (wolf suit) | Open (random outfit, upstream behaviour) |

## Summary of the report

- **Top problems:** load time, glyph readability, silent blocked moves, no fast travel or goal, an overwhelming crafting list, unfriendly capacity and wield wording, odd starts, dangerous stray keys, and easy-to-miss direction prompts.
- **Worked well:** the welcome card, the controls strip, `Q` stash and multi-pickup, the look command, the sidebar compass with its monster list, foraging messages, and click-to-travel once found.

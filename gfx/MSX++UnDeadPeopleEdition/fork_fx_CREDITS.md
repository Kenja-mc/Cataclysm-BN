# fork_fx.png — status effect overlay animation frames

This sheet holds the looping overlay frames drawn on creatures for visible status
effects (bleeding, poisoned or sick, stunned or dazed, asleep, cold or wet), the
way Sword of the Stars: The Pit shows status icons over units.

No new artwork was drawn for this sheet, and no AI tool generated any pixel: every
tile is a crop of a sprite that ships inside this very tileset
(`gfx/MSX++UnDeadPeopleEdition`), placed unchanged inside a 64×80 sprite cell at
64×80 (the same cell size as `large_stuff.png`, with its `sprite_offset_x` / `sprite_offset_y`
so the overlays sit on the creature exactly where the static `overlay_effect_*`
icons already sit). The only edits are the vertical offsets listed below, which
are what make the loops move.

## Source

All source sprites come from **Cataclysm: Bright Nights**' own default tileset
(`UNDEAD_PEOPLE_BASE` / MSX++ UnDead People Edition) in this repository, sheet
`large_stuff.png` (64×80 sprites). Those sprites come from the Cataclysm tileset
community, which like this project is licensed under the Creative Commons
Attribution-ShareAlike 3.0 Unported License — see `LICENSE.txt` and
`fork_fill_CREDITS.md` for the upstream links and per-tile attribution.

## Tiles

| Tile id | Frames | Source sprite (`large_stuff.png`) | What was done |
| --- | --- | --- | --- |
| `overlay_fx_bleed_0…3` | 4 | `overlay_effect_bleed`, sprite 18627 | blood droplet sprite, lifted 12, 8, 4 and 0 px, so the drip falls |
| `overlay_fx_toxic_0…3` | 4 | `overlay_effect_poison`, sprite 18645 | green poison icon, bobbed down/up/down |
| `overlay_fx_dizzy_0…3` | 4 | `overlay_effect_stunned`, sprite 18648 and `overlay_effect_dazed`, sprite 18632 | the star and the spiral icons alternate, both bobbed |
| `overlay_fx_sleep_0…3` | 4 | `overlay_effect_sleep`, sprite 18647 | "zz" bubble, bobbed |
| `overlay_fx_cold_0…3` | 4 | `overlay_effect_common_cold`, sprite 18631 | blue snowflake, bobbed |

Sprite numbers in the table are global `tiles-new` indices, not sheet-local ones.

Burning creatures keep using `overlay_effect_onfire`, which already carries six
animated frames in `tile_config.json`; no copy was made for it.

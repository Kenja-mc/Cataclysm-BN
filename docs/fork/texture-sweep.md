# Texture sweep, 2026-10-22

A review of the nine tilesets in `gfx/` and the sheets in `data/json/external_tileset/`: identical
sprites, visual clarity, and licenses. Full reports, contact sheets and the scripts that produced
them are on the `research/textures` branch under `docs/fork/research/textures/`. Sprite references
use `sheet#index`, the global index in `tile_config.json`.

## Fixed

| Tileset | Problem | Fix |
|---|---|---|
| BrownLikeBears | A second `battleaxe` entry pointed at `tiles.png#861`, which is fully transparent; later entries replace earlier ones (`tileset::create_tile_type`), so the battleaxe and its fake and inferior variants drew nothing. | The variants use the drawn battleaxe sprite `#489`; the duplicate entry is gone. |
| ChestHole16 | Eight dinosaurs (`mon_spinosaurus` to `mon_utahraptor`) were remapped to `tree.png` cells 72 to 79, which are empty, after `tiles.png` had already given them art. | The empty remaps are removed, so the `tiles.png` art draws. |

## Identical sprites

88,140 sprite cells hashed across 28 sheet groups; 541 images are shipped identically in two
tilesets (RetroDays and RetroDays+ share 346). The groups that matter in play:

| Tileset | Sprite | Ids drawn identically |
|---|---|---|
| RetroDays+ and RetroDays | `tiles.png#2615` | nine dog breeds, including the mutant `mon_dog_thing` |
| ChestHole16 | `tiles.png#1645` | chipmunk, groundhog, lemming, mink, otter, weasel |
| external `DP_dmd` | `External_Tileset_DP_dmd.png#28` | the factionless and the hostile `mon_mutant_medical_summon` |
| HitButton iso | `HitButton_iso.png#2349` | centipede, dragonfly, mosquito, small wasp: one yellow pixel |
| RetroDays+ (and two more) | `tiles.png#896` | 35 liquids, including methanol, ethanol and water |
| MSX++ (default) | `normal_items.png#2690` | 26 chemicals and drinks, including bleach, sulphuric acid and gin |
| Hoder's | `hodertiles.png#551`, `#1105` | 30 ammunition calibres; adderall, codeine, oxycodone and other drugs |

Only the item name tells these apart. The worst cases are the mutant dog drawn as a pet, the hostile
and harmless summons sharing a sprite, and drinkable water drawn like methanol.

## Clarity, default tileset (MSX++ UnDeadPeople Edition)

| Rank | Problem | Evidence | Suggested fix |
|---|---|---|---|
| 1 | Locked doors look exactly like closed ones. | `t_door_c` `#12558` and `t_door_locked` `#12591` differ in 0 pixels; the same holds for the alarm, interior, peephole, barred and metal pairs. | UltimateCataclysm already draws a locked door with a keyhole (`normal.png#3240`). |
| 2 | 233 tile ids point at `normal_stuff.png#9304`, which is fully transparent. | 93 are not character overlays: `grass`, `underbrush`, `muscle`, `nectar`, `toolset`, all nine `vp_plating_*`, `tr_ledge`, `fd_shadow`. Plating, ledges and shadows may be blank on purpose; harvested plants and tools are not. | Repoint the items at existing art or drop the entry so the letter fallback draws. |
| 3 | Several zombies have almost the same brightness as grass. | Luminance difference against `t_grass`: fat zombie 2.3, spitter 1.8, child 3.5, runner 4.3. | Outline or darken the sprites. |
| 4 | Clothed zombies read as living people; zombie animals keep the living animal's body and colour. | `mon_zombie_child` `#8343`; `mon_dog` and `mon_zombie_dog` overlap 97 %. | A hostile cue (skin tone, eyes, outline) on zombie variants. |
| 5 | Wooden doors have the floor's brightness; open and closed doors have the same mean colour. | `t_door_c` 53.7 against `t_floor` 50.1. | A darker frame or an open-door gap. |
| 6 | Ramps look like pits. | `t_ramp_up_low` and `t_pit` share their silhouette. | UltimateCataclysm `normal.png#3633` shows a shaded slope. |
| 7 | Field overlays are flat squares that hide the floor and show tile seams. | `fd_acid` `normal_fields.png#10577`. | UltimateCataclysm `normal.png#1125` is a same-size acid splatter. |
| 8 | Small loot disappears on wood floor. | First aid kit, beans and lighter all within 3 luminance points of `t_floor`. | A one-pixel dark outline on item sprites. |
| 9 | The player and NPCs share a sprite. | `#8852` and `#8850` are identical. | A palette shift for NPCs, as RetroDays+ and BrownLikeBears do. |

The ChestHole16, Hoder's and HitButton iso sets share the invisible-lock problem.

## Licenses

The credits index (`asset-credits.md`) now names the authors of every bundled tileset. Two findings
change how the bundle is described:

- **RetroDays is CC BY-SA 4.0, not 3.0.** The author's page said so before the CDDA import
  ([May 2014 archive](http://web.archive.org/web/20140508002706/http://www.nexusmods.com/cataclysmdarkdaysahead/mods/1)).
  RetroDays+, BrownLikeBears and the ASCII sheet derive from it. Shipping a 4.0 work alongside
  3.0 content is allowed when each keeps its own license; mixing their sprites into one sheet is
  not covered.
- **The default tileset's provenance is unresolved.** CDDA removed the MShock-derived tilesets in
  2019 after a `jerky` sprite was traced to the Minecraft HarvestCraft mod
  ([PR 34196](https://github.com/CleverRaven/Cataclysm-DDA/pull/34196)); the maintainers judged
  every sprite inherited through the Raga tileset suspect. MSX++ UnDeadPeople Edition descends
  from that family, and it also uses "Nearly Dead" art by permission of its authors, with no
  license text. The `jerky` sprite in this checkout (`normal_items.png#2823`) does not match the
  image on today's HarvestCraft wiki, so this sweep could not confirm or clear it.

Outside art that is safe to add, by license:

| Source | License | Size | Fits |
|---|---|---|---|
| [DCSS tiles](https://github.com/crawl/tiles) | CC0, except a published list of files with unknown licenses | 32 px top-down | Creatures, items, terrain, effects |
| [Kenney 1-Bit Pack](https://kenney.nl/assets/1-bit-pack) and Roguelike packs | CC0 | 16 px | High-readability glyph art |
| [game-icons.net](https://game-icons.net/) | CC BY 3.0 | vector | Status and UI icons |
| [DawnLike](https://opengameart.org/content/dawnlike-16x16-universal-rogue-like-tileset-v181) | CC BY 4.0 | 16 px | General roguelike set |

Not usable: Oryx Design Lab (redistribution forbidden), anything NC or ND, GPL-only art, and
forum permissions without license text.

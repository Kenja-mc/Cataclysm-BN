# Visual clarity sweep of the bundled tilesets

Scope: the fork default `gfx/MSX++UnDeadPeopleEdition/` (UNDEAD_PEOPLE_BASE, "MSX++ UnDeadPeople
Edition") in depth, then the other eight tilesets in `gfx/` briefly. Research only. No repo file was
modified.

All sprite references use `sheet#index` where `index` is the global sprite number the game loads
(sheet order and `(w/sprite_w)*(h/sprite_h)` per sheet, as in `tileset_loader::load_tileset`).
`tile_config.json` in MSX++ already stores global indices, so the number printed here is the number
in that file.

## How this was measured

* Sprite resolution: `idx.py` parses `gfx/<ts>/tile_config.json`, works out each sheet's sprite
  count and base offset, and maps a tile id to `(sheet, pixel box)`.
* Contact sheets: `mk.py` crops each sprite, optionally composites the tile's `bg` sprite (shadows)
  and a tiled floor, scales with `-filter point`, and labels each cell with the tile id and
  `sheet#index`.
* Numbers: `metrics.py` reports

  * `cov` = fraction of the tile's pixels with alpha > 127
  * `L` = mean luminance of those pixels, `L = 0.2126R + 0.7152G + 0.0722B` on 0..255 sRGB values
  * `dL` = |L(sprite) - L(floor)| for the usual floor under that tile
  * `changed` = percentage of the 1024 tile pixels whose max channel difference exceeds 8
  * `maskIoU` = overlap of the two silhouettes (alpha > 127)
  * `colourd` = Euclidean distance between mean opaque colours, 0..441
  * `deut` = the same distance after deuteranopia simulation.

Deuteranopia simulation matrix, applied to sRGB channel values with
`magick in.png -color-matrix "0.625 0.375 0 0.7 0.3 0 0 0.3 0.7" out.png`:

| 0.625 | 0.375 | 0.0 |
| 0.700 | 0.300 | 0.0 |
| 0.000 | 0.300 | 0.700 |

This is the common Viénot/Brettel-style approximation. It is a screen-space approximation on
gamma-encoded values, not a colour-managed LMS simulation.

## Ranked findings, default tileset (worst first)

| # | Problem | Tile ids | Sheet#index | Evidence | Why it matters in play | Fix |
|---|---|---|---|---|---|---|
| 1 | 233 tile ids resolve to a fully transparent sprite, so nothing is drawn (93 of them are not character overlays) | `grass`, `nectar`, `underbrush`, `muscle`, `software`, `toolset`, `fd_shadow`, `vp_plating_*` (9 variants), `tr_ledge`, `tr_glass_pit`, `tr_glow`, `v29_turret`, `arcfurnace`, `butter_churn`, `apparatus` | `normal_stuff.png#9304` (alpha mean 0.000) | Alpha mean of the referenced sprite is exactly 0.0, "uniq=1" colour. See `clarity/18_invisible_items.png`: the cells are bare floor | Harvestable items (`grass`, `nectar`, `underbrush`), the integrated toolset, and all nine vehicle armour plates are invisible on the ground or on the vehicle. A player cannot see what is lying there or that a vehicle is armoured | The id exists in the tileset, so the renderer uses the transparent sprite instead of an ASCII glyph. Either delete those `fg` entries so the ASCII fallback draws, or repoint them at art already in the sheet: `grass` -> `wild_herbs` `normal_items.png#3581`, `nectar` -> `normal_items.png#4253` (`straw_pile`), `underbrush` -> `plant_fibre` `normal_items.png#362`. For plating, copy `vp_plating_steel` from `gfx/UltimateCataclysm/` (`fillerhoder.png#8464`, a riveted plate) |
| 2 | Locked and closed doors are pixel-identical | `t_door_c` vs `t_door_locked`, `t_door_locked_alarm`, `t_door_locked_interior`; `t_door_c_peep` vs `t_door_locked_peep`; `t_door_bar_c` vs `t_door_bar_locked`; `t_door_metal_c` vs `t_door_metal_pickable` | `normal_terrain.png#12558` / `#12591`; `#12561` / `#12594`; `#12550` / `#12551`; `#12599` / `#12607` | `changed = 0.0%`, `meanabs = 0.0` for every pair | The player must walk into a door, or read the message log, to learn it is locked. Every locked house door is a wasted move | Add a visible lock mark. UltiCa already draws one: `t_door_locked` = `gfx/UltimateCataclysm/normal.png#3240`, only 4.1% of pixels differ from its closed door, but that 4.1% is a yellow keyhole. RetroDays uses 11.0% and BrownLikeBears 13.5%. Copying the keyhole pixels into the four locked MSX sprites keeps the CC BY-SA lineage and needs no new art |
| 3 | Wooden doors have the same luminance as the wooden floor they stand on | `t_door_c`, `t_door_o`, `t_door_b` | `normal_terrain.png#12558`, `#12608`, `#12549` | Sprite L = 53.7 / 53.3 / 50.0 against `t_floor` L = 50.1, so `dL` = 3.6 / 3.2 / 0.2 | In a wooden house a closed door, an open door and a smashed door are all brown-on-brown. Doorways disappear and the player bumps walls while fleeing | Outline the door frame in near-black and lighten the door panel by ~20 luminance units against the `#9190` floor, or swap in the door art of `gfx/UltimateCataclysm/normal.png#3240`-family, where the panel is darker than the floor and the frame is light |
| 4 | Most zombie variants are the same brightness as grass | `mon_zombie_fat`, `mon_zombie_spitter`, `mon_zombie_child`, `mon_zombie_runner`, `mon_zombie_acidic`, `mon_zombie` | `normal_monsters.png#8266`, `#8331`, `#8343`, `#8551`, `#8325`, `#8194` | `dL` against `t_grass` (L = 70.1) = 2.3 / 1.8 / 3.5 / 4.3 / 8.9 / 13.4 | Zombies standing on open ground blend into the terrain at native zoom. This is the most common threat in the game | Darken the trousers/torso of the pale variants, or add a dark outline. The tileset already ships a readable dark palette in UltiCa: `mon_zombie` = `gfx/UltimateCataclysm/tall.png#4544`-family (green skin, dark outline) |
| 5 | Humanoid zombie variants read as living people | `mon_zombie_child` (blonde girl, blue skirt), `mon_zombie_soldier`, `mon_zombie_grenadier`, `mon_zombie_fireman`, `mon_zombie_medical`, `mon_zombie_cop` | `normal_monsters.png#8343`, `#8648`, `#8378`, `#8283`, `#8440`, `#8230` | `mon_zombie_child` vs `mon_zombie` `maskIoU 0.64`, `colourd 14.1`; the sampled zombies use human skin tones, not a green/grey convention | A hostile child zombie, soldier zombie or doctor zombie looks like an NPC, so the player hesitates or walks into melee | Use the green/grey skin convention UltiCa uses (`gfx/UltimateCataclysm/tall.png` human bodies) or add a red-eye overlay to every `mon_zombie_*` that lacks one. `mon_zombie_bio_op` (`normal_monsters.png#8636`) already does this with red eyes and reads as hostile |
| 6 | Zombie animals are the same body and colour as the living animal | `mon_dog` vs `mon_zombie_dog`, `mon_horse` vs `mon_zombie_horse` | `normal_monsters.png#7800` vs `#8160`; `large_stuff.png#18427` vs `#18552` | `maskIoU 0.97`, `colourd 8.0` for the dogs; both horses are the same brown | The only cue is a small red ribcage patch. Behind a bush, at the screen edge, or facing away, a hostile dog is indistinguishable from a pet dog. Dogs are fast and crippling | Reuse `mon_zombie_pig` (`normal_monsters.png#8171`, grey hide with visible ribs) as the treatment: desaturate the zombie dog and horse hides and enlarge the ribcage patch |
| 7 | Flat overlay fields hide the floor and show a tile grid | `fd_acid`, `fd_sludge`, `fd_fog`, `fd_gibs_flesh`, `fd_sap` | `normal_fields.png#10577`, `#10936`, `#10711`, `#10748`, `#10901` | `fd_acid` alpha mean 0.76 with 6 distinct colours, `fd_sludge` 0.93 with 76, `fd_fog` 0.48 with 31, `fd_gibs_flesh` 0.89 with 167. Tiled 3x3 in `clarity/25_field_tiling.png` they read as flat slabs with visible cell seams | An acid pool covers what is underneath. Items, traps, and the edge of deep water vanish under a solid green rectangle, and the seams telegraph the tile lattice | Give the overlays texture and lower alpha: `fd_acid` should be a splatter at ~40% alpha with ragged edges. `gfx/UltimateCataclysm/normal.png#1125` is an acid splatter of the same 32x32 size, CC BY-SA lineage, ready to copy |
| 8 | `fd_incendiary` is drawn as grey smoke, and `fd_shadow` draws nothing | `fd_incendiary`, `fd_shadow` | `normal_fields.png#10826` (grey puff); `normal_stuff.png#9304` (transparent) | Visual check, `clarity/11_fields_3x.png`. `fd_flame_burst` (`large_stuff.png#18169`) next to it is a red flame | Burning ground that does not look like fire gets walked into. `fd_shadow` being invisible removes the only cue for a lighting effect | Repoint `fd_incendiary` at a flame sprite already in the repo: `large_stuff.png#18158` (`fd_flame_burst`) or `large_stuff.png#18163` (`fd_fire`). Give `fd_shadow` a dark translucent overlay |
| 9 | Ramps are opaque black tiles with an arrow, indistinguishable from pits | `t_ramp_up_low`, `t_ramp_up_high`, `t_ramp_down_low`, `t_ramp_down_high` vs `t_pit`, `t_pit_shallow` | `normal_terrain.png#16801`, `#16800`, `#16799`, `#16798`; `t_pit` `#15628` | `t_ramp_up_low` vs `t_pit`: `maskIoU 1.00`, `colourd 15.0` on the same 32x32 footprint. Ramps are L = 28.2, `t_pit` is L = 20.6 (`normal_terrain.png#15628`). Up vs down differ by arrow only, `colourd 8.7`; low vs high differ by 4.3% of pixels | A ramp looks like a hole with an arrow. In a dark room, or with a vehicle, the player cannot tell a ramp from a pit, and up from down | Replace with a slope: UltiCa `t_ramp_up_low` = `gfx/UltimateCataclysm/normal.png#3633` shows a shaded slope plus an arrow at the same 32x32 size |
| 10 | Stairs are almost invisible on outdoor ground, and up/down differ only by a small arrow | `t_stairs_up`, `t_stairs_down` | `large_terrain.png#19093`, `#19091` | Against `t_grass`, `dL` = 2.3 / 2.1. Against each other `maskIoU 0.99`, `colourd 7.3` | A storm-cellar entrance in a field is a faint shadow: the sprite covers only 21% of the tile and its mean luminance matches the grass, so the arrow is the whole cue. Players miss the stairs and cannot tell which way they go | Keep the arrow but add a hard rim to the stairwell, or reuse RetroDays+ `t_stairs_up/down` (`gfx/RetroDays+Tileset/tiles.png`, bright yellow arrows on a dark well) which reads at 10x10 |
| 11 | Loot disappears into the wood floor by luminance | `1st_aid` (dL 2.0), `can_beans` (2.9), `lighter` (1.1), `crowbar` (8.3), `energy_drink` (13.6), `556` (15.1) | `normal_items.png#3152`, `#3346`, `#6405`, `#6310`, `#2923`, `#30` | Sprite L vs `t_floor` L = 50.1, see `clarity/14_loot_1x_floor.png` | The first-aid kit and the tin can are the same grey as a plank floor. At native size the player walks over loot | Give pickups a light rim or a dark drop shadow. MSX already uses a shadow sprite `normal_stuff.png#9173` as `bg` for many items; adding it to `1st_aid`, `can_beans`, `lighter`, `crowbar` is a JSON-only change |
| 12 | Ammo types are distinguishable only by tiny printed text | `556` vs `556_incendiary`; `9mm` vs `223` | `normal_items.png#30` vs `#31`; `#234` vs `#29` | 556 pair: `maskIoU 0.86`, `colourd 12.6`, same dark grey box silhouette. 9mm vs 223: `colourd 18.8`, both yellow cartridge clusters | Reloading the wrong magazine, or grabbing the wrong ammo in a fight, is a real risk when both boxes are dark grey 12 px squares | Colour-code the box lids (already done for `9mmfmj`, `normal_items.png#235`, which prints its calibre). Apply the same treatment to 556 and 223 |
| 13 | Vehicle body parts are flat red squares | `vp_board`, `vp_roof`, `vp_aisle`, `vp_trunk`, `vp_door_trunk` | `normal_vehicle_parts.png#16819`, `normal_furniture.png#11718`, `normal_vehicle_parts.png#17674`, `#17850`, `#17740` | `vp_board` vs `vp_roof`: `maskIoU 1.00`, `colourd 25.6`. Both are uniform 32x32 fills, see `clarity/dbg_veh.png` | When repairing a vehicle, the player cannot tell an aisle from a board or a roof. Red fill also merges doors with body panels | Use textured plates. UltiCa has a riveted plate at `fillerhoder.png#8464`; `vp_cargo_space` (`normal_vehicle_parts.png#17693`) shows the level of texture that works |
| 14 | The player and an NPC have identical sprites | `player_male` vs `npc_male`, `player_female` vs `npc_female` | `normal_character.png#8852` vs `#8850`, `#8851` vs `#8849` | `maskIoU 1.00`, `colourd 0.0` | When unclothed (swimming, showering, stripped) the player and any NPC wearing the same items are identical. Friendly NPC and yourself are the same white mannequin | Colouring the NPC body (as RetroDays+ does, purple NPC vs white player) or adding a marker overlay to the player is enough. RetroDays+ reference: `gfx/RetroDays+Tileset/tiles.png`, `npc_male` |
| 15 | Dark and glowing monsters lose their silhouette | `mon_zombie_kevlar_1` (L 14.5), `mon_zombie_electric` (coverage 12%), `mon_zombie_smoker` (L 122.7 with 15% semi-transparent pixels) | `normal_monsters.png#8642`, `large_stuff.png#18568`, `normal_monsters.png#8572` | `mon_zombie_kevlar_1` is a black mass with two red eyes. `mon_zombie_electric` covers 12% of the tile: the body is an outline and the rest is glow | The kevlar zombie is a black blob on any dark floor. The electric zombie's glow washes out its body so its pose and direction cannot be read | Add a rim light to `#8642` (the tileset already rim-lights `mon_zombie_armored`, `#8634`) and draw `mon_zombie_electric` with a solid body under the glow |
| 16 | Water depth and pool type are inconsistent | `t_water_sh` vs `t_water_dp`; `t_water_pool` vs `t_water_pool_shallow` | `normal_terrain.png#14646` vs `#14378`; `#14578` vs `#14612` | Shallow vs deep: `maskIoU 1.00`, `colourd 36.4`. Pool shallow is grey while pool is blue-green (visual check, `clarity/17_water_3x.png`) | Shallow water is safe, deep water drowns you, but the two look alike. The shallow pool reads as concrete | Make depth a value difference of at least 60 units, and repaint `t_water_pool_shallow` with the `t_water_sh` palette |
| 17 | Several window states are invisible or near-invisible | `t_window` vs `t_window_alarm`; `t_window_domestic` vs `t_window_no_curtains`; `t_window_frame` vs `t_window_empty` | `normal_terrain.png#16756` vs `#16757`; `#16765` vs `#16771`; `#16770` vs `#16767` | Alarm: `changed 0.0%`. Domestic vs no curtains: `colourd 12.5`, same light-blue grid. Frame vs empty: `changed 11.1%` | An alarmed window cannot be discovered, and a curtained window shows no curtain | Alarm state: reuse the small yellow warning glyph MSX already draws for `t_door_locked_alarm`-style tiles. `t_window_domestic` needs an actual curtain: RetroDays+ `t_window_domestic` draws a curtain band |
| 18 | Red/green pairs collapse for deuteranopes | `t_door_red_c` vs `t_door_green_c`; `t_wall_r` vs `t_wall_g`; `t_window_stained_red` vs `t_window_stained_green` | `normal_terrain.png#12611` vs `#12584`; `#16505` vs `#16343`; `#16779` vs `#16778` | Deuteranope colour distance kept: 26%, 47%, 50% of the normal distance. Absolute simulated distance for the doors is 8.2 out of 441 | A red door and a green door become the same brown. Painted walls of a base become one colour | Differentiate by lightness, not hue. `t_wall_r` (mean RGB 120,26,26, L 46.1) and `t_wall_g` (62,117,61, L 101.5) survive the simulation only because of that 55 unit luminance gap; the painted doors (57,27,24 vs 40,53,23) have no such gap and fail |
| 19 | One hostile human variant is drawn from the scratch sheet in a different style | `mon_feral_soldier` | `Temporary.png#19174`, `#19177` | Compare `clarity/24_char_style.png`: the feral soldier is a side-facing, broad-shouldered figure, while `mon_feral_human_pipe` (`normal_monsters.png#7443`) and `mon_feral_human_crowbar` (`#7432`) are front-facing red-eyed figures | The most dangerous feral human variant is the one that looks least like the others, so it reads as a soldier NPC or a new creature | Move the two sprites into `normal_monsters.png` next to the other feral humans, or redraw them in the same front-facing pose |
| 20 | Real content lives in files named `Temporary*` | 794 tile ids resolve into `Temporary.png`, `Temporary-maptiles.png`, `Temporary-Maptiles-Large.png` | file level | Sheet census: 794 ids in total, 83 in `Temporary.png`, 667 in `Temporary-maptiles.png`, 44 in `Temporary-Maptiles-Large.png` | Not a drawing fault, but a maintenance hazard: a future cleanup of "temporary" files deletes live mapgen and monster art | Rename to `mapgen_symbols.png` and `mapgen_symbols_large.png`, or fold them into `normal_terrain.png` |

## Confusion pairs worth knowing

| Pair | maskIoU | colourd | Note |
|---|---|---|---|
| `mon_dog` / `mon_zombie_dog` | 0.97 | 8.0 | hostile dog looks like a pet |
| `mon_horse` / `mon_zombie_horse` | 0.98 | 14.1 | same defect on the horse |
| `t_door_c` / `t_door_locked` | 1.00 | 0.0 | identical |
| `t_door_bar_c` / `t_door_bar_locked` | 1.00 | 0.0 | identical |
| `t_window` / `t_window_alarm` | 1.00 | 0.0 | identical |
| `t_ramp_up_low` / `t_ramp_up_high` | 1.00 | 8.7 | 4.3% of pixels differ |
| `t_ramp_up_low` / `t_pit` | 1.00 | 15.0 | ramp reads as a hole (L 28.2 vs 20.6) |
| `t_stairs_up` / `t_stairs_down` | 0.99 | 7.3 | arrow direction is the only cue |
| `t_water_sh` / `t_water_dp` | 1.00 | 36.4 | safe water vs drowning water |
| `vp_board` / `vp_roof` | 1.00 | 25.6 | flat red squares |
| `556` / `556_incendiary` | 0.86 | 12.6 | same box, same grey |
| `player_male` / `npc_male` | 1.00 | 0.0 | identical |
| `t_door_c` / `t_door_o` | 0.56 | 1.0 | same mean colour, only the shape differs |
| `t_wall_wood` / `t_door_c` | 1.00 | 37.7 | both brown planks |

## Colour-vision check

`clarity/19_color_pairs.png` is the normal view; `clarity/20_color_pairs_deuteranopia.png` is the same
sheet after the matrix above. Findings that survive the simulation:

* `t_door_red_c` and `t_door_green_c` become indistinguishable as shapes and as colour.
* `t_wall_r` (L 46.1) and `t_wall_g` (L 101.5) remain distinguishable, but through a 55 unit luminance
gap, not through hue.
* `fd_blood` and `fd_blood_veggy` stay apart (55% of the distance survives).
* `fd_fire` and `fd_acid` stay apart (fire is bright, acid is dark green).
* `t_window_stained_red` and `t_window_stained_green` keep half their distance. They are acceptable
  but only because the windows also differ in pattern.

## Other tilesets

One contact sheet each, same 20 ids, in `clarity/x_<tileset>_<scale>.png`. Native tile sizes differ:
10x10 (RetroDays, RetroDays+, ASCIITiles), 16x16 (ChestHole16, Hoder), 20x20 (BrownLikeBears),
32x32 (UltiCa mixed, MSX). The sheets are upscaled with `-filter point`.

| Tileset | Observations (all verified on the sheets or by `metrics.py`) |
|---|---|
| `UltimateCataclysm` | Best reference art of the eight. Locked door differs from closed by a keyhole (4.1% of pixels). `1st_aid` (`normal.png#1731`) is a red bag with a white cross, high contrast, unlike MSX's grey box. `t_ramp_up_low` (`normal.png#3633`) is a shaded slope. `fd_acid` (`normal.png#1125`) is a splatter. `t_water_dp` (`normal.png#4405`) is visibly darker than shallow water. Weak spot: 186 ids still point at a blank sprite, and `t_door_c`/`t_door_locked` differ by only 4% of pixels, which is easy to miss at 32 px |
| `ChestHole16Tileset` | 16x16. Locked door identical to closed (0.0%). Window open/closed only 30.5% changed at a small tile size. Its water shallow/deep are the same blue. 134 ids point at a blank sprite, most of them in the 4096-sprite `fallback.png` |
| `RetroDaysTileset` | 10x10, very legible. Locked door differs by 11% of pixels (visible padlock dot). Player white, NPC magenta: instant recognition, the fix MSX needs for finding 14. Stairs use a bright yellow arrow. Only 4 blank ids |
| `RetroDays+Tileset` | Same family as RetroDays, plus a 20x20 sheet. Stairs up/down arrows are the clearest of all nine tilesets. 6 blank ids |
| `BrownLikeBears` | 20x20. Zombies colour-coded: normal zombie bright green, brute bright red. Excellent for threat reading, and a cheap convention for MSX. Locked door 13.5% different (small keyhole). Stairs are a `+` mark, cryptic |
| `HoderTileset` | 16x16. Locked door identical to closed (0.0%). No `t_water_sh`/`t_water_dp` entries at all. `water_clean` is a black droplet, low contrast on dark floors. 379 blank sprites but only 6 ids |
| `HitButton_iso` | Isometric 16x20. Locked door identical to closed (0.0%) and window open/closed only 5.6% different, the worst state-visibility of the set |
| `ASCIITileset` | Only 56 tile ids, 38 sprite entries. Nearly everything is ASCII, so the clarity questions above do not apply. Not a source of art for fixes |

## Contact sheets

| File | Content |
|---|---|
| `clarity/01_chars_3x.png`, `01b_chars_1x_floor.png` | player, NPC, feral humans, soldier and cop zombies |
| `clarity/02_zombies_3x.png`, `03_zombies_1x_grass.png` | 24 zombie variants, raw and at native size on grass |
| `clarity/04_animals_3x.png`, `04b_animals_1x_grass.png` | living animals next to their zombie versions |
| `clarity/05_doors_3x.png`, `06_doors_1x_floor.png` | 33 door tiles, raw and at native size on a wood floor |
| `clarity/07_windows_walls_3x.png`, `08_fences_3x.png` | windows, walls, fences and gates |
| `clarity/09_stairs_3x.png`, `10_stairs_1x_grass.png` | stairs, ramps, ladders |
| `clarity/11_fields_3x.png` | fields: fire, smoke, acid, blood, gas, plasma |
| `clarity/13_loot_3x.png`, `14_loot_1x_floor.png` | ammo, medicine, food, tools |
| `clarity/15_vehicles_3x.png` | vehicle parts that change behaviour |
| `clarity/17_water_3x.png` | water shallow, deep, murky, pool, corners |
| `clarity/18_invisible_items.png` | items whose sprite is transparent: cells are bare floor |
| `clarity/19_color_pairs.png`, `20_color_pairs_deuteranopia.png` | colour pairs, normal and simulated |
| `clarity/21_fork_fill.png` | the fork's own additions (`fork_fill.png`, `fork_fx.png`) |
| `clarity/22_traps_3x.png` | traps |
| `clarity/23_ultica_fix_sources.png` | alternative art for the fixes, from UltiCa |
| `clarity/24_char_style.png` | style break in `mon_feral_soldier` |
| `clarity/25_field_tiling.png` | fields tiled 3x3 to expose seams |
| `clarity/dbg_*.png` | detail views cited above (doors, ramps, pit vs ramp, vehicle parts) |
| `clarity/x_<tileset>_*.png` | the 20-id comparison sheet for each other tileset |

## Commands

Everything is reproducible with three small scripts in `/tmp/texture-sweep/`:

```sh
# sprite index resolution
python3 idx.py sheets MSX++UnDeadPeopleEdition
python3 idx.py find MSX++UnDeadPeopleEdition "t_door"
python3 idx.py one  MSX++UnDeadPeopleEdition t_door_c t_door_locked

# one labelled contact sheet (ids on stdin, "label | id" allowed, t_water_sh[center] for a
# multitile variant, spr:12345 for a raw sprite)
printf 't_door_c\nt_door_o\n' | python3 mk.py --ts MSX++UnDeadPeopleEdition \
    --out clarity/06_doors_1x_floor.png --cols 6 --scale 1 --post-scale 5 --floor t_floor

# metrics
python3 metrics.py MSX++UnDeadPeopleEdition diff t_door_c,t_door_locked
python3 metrics.py MSX++UnDeadPeopleEdition sim  mon_dog,mon_zombie_dog
python3 metrics.py MSX++UnDeadPeopleEdition stats t_floor 1st_aid can_beans lighter
python3 metrics.py MSX++UnDeadPeopleEdition cvd t_door_red_c,t_door_green_c

# deuteranopia simulation
magick clarity/19_color_pairs.png -color-matrix "0.625 0.375 0 0.7 0.3 0 0 0.3 0.7" \
    clarity/20_color_pairs_deuteranopia.png

# rebuild everything
./build.sh
```

`/tmp/texture-sweep/build.sh` rebuilds every sheet in about 50 seconds without running the game.

## Limits and inferences

* [INFERENCE] Sprite counts and indices follow `tileset_loader::load_tileset` integer division, so
  the 31-pixel tail of `normal_items.png` (512x14751) is not addressable. No tile id was found that
  depends on it.
* [INFERENCE] "Rendered as nothing" for the transparent sprites is derived from the loader keeping
  the entry and the renderer blitting the sprite. The game was not run, per the task constraints.
* Luminance contrast is computed from sprite pixels only, not from a composited frame at night, in
  the rain, or under a light source. Night and season variants (`*_season_winter`) were not reviewed.
* Humour, flavour and non-combat sprites were not reviewed. Furniture, bionics, mutations, and mod
  tilesets are out of scope for this ticket.

# Overhaul Soundpack - Sources & Licenses

Kenney and verified Freesound-derived files below are **CC0 1.0**; the
project-generated synthetic gunshots in this pack are covered by the
project default **CC BY-SA 3.0** (repository `LICENSE.txt`). No blanket
CC0 claim is made for the synthetic files, and no user CC0 grant is
asserted for them. Most CC0 files are taken from Kenney.nl asset packs;
the dirt footsteps and obstacle climbing clips are from freesound.org
recordings (see the per-file table below).

| Pack                                                     | Source                                                       | License                                                     |
| -------------------------------------------------------- | ------------------------------------------------------------ | ----------------------------------------------------------- |
| Impact Sounds 1.0                                        | http://kenney.nl/assets/impact-sounds                        | CC0 1.0 (http://creativecommons.org/publicdomain/zero/1.0/) |
| Digital Audio                                            | http://kenney.nl/assets/digital-audio                        | CC0 1.0                                                     |
| Interface Sounds 1.0                                     | http://kenney.nl/assets/interface-sounds                     | CC0 1.0                                                     |
| RPG Audio                                                | http://kenney.nl/assets/rpg-audio                            | CC0 1.0                                                     |
| freesound.org "Left Gravel Footstep" recordings          | see per-file table below (Ali_6868, pack "Gravel Footsteps") | CC0 1.0                                                     |
| freesound.org "Car - Climbing onto someone and back off" | https://freesound.org/s/574247/ (MWsfx)                      | CC0 1.0                                                     |

Author: Kenney Vleugels (www.kenney.nl)
Creation dates: impact-sounds 2019-12-19; interface-sounds 2020-02-11; digital-audio/RPG-audio ~2019-2020.

### freesound.org files (each license verified on its freesound page)

Taken via the CC-Sounds repository's CC0-curated copies
(https://github.com/Fris0uman/CDDA-Soundpacks, `sound/CC-Sounds/plmove`), resampled from
48 kHz to the pack's 44100 Hz mono and peak-normalized to match the other footstep clips.

| File                       | Original (freesound)                                                       | Author   | License |
| -------------------------- | -------------------------------------------------------------------------- | -------- | ------- |
| footsteps/dirt_000.ogg     | "Left Gravel Footstep 2" https://freesound.org/s/384871/                   | Ali_6868 | CC0 1.0 |
| footsteps/dirt_001.ogg     | "Left Gravel Footstep 3" https://freesound.org/s/384872/                   | Ali_6868 | CC0 1.0 |
| footsteps/dirt_002.ogg     | "Left Gravel Footstep 1" https://freesound.org/s/384873/                   | Ali_6868 | CC0 1.0 |
| footsteps/dirt_003.ogg     | "Left Gravel Footstep 5" https://freesound.org/s/384874/                   | Ali_6868 | CC0 1.0 |
| footsteps/dirt_004.ogg     | "Left Gravel Footstep 4" https://freesound.org/s/384875/                   | Ali_6868 | CC0 1.0 |
| footsteps/obstacle_000.ogg | "Car - Climbing onto someone and back off" https://freesound.org/s/574247/ | MWsfx    | CC0 1.0 |
| footsteps/obstacle_001.ogg | "Car - Climbing onto someone and back off" https://freesound.org/s/574247/ | MWsfx    | CC0 1.0 |

## Sound effect mapping (id -> file set)

| id                                | variant                                                                                                                                                                                                                                                       | files                                                                                                                            |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| plmove                            | walk_grass                                                                                                                                                                                                                                                    | footsteps/grass_00{0-4}.ogg                                                                                                      |
| plmove                            | walk_dirt                                                                                                                                                                                                                                                     | footsteps/dirt_00{0-4}.ogg                                                                                                       |
| plmove                            | walk_tarmac                                                                                                                                                                                                                                                   | footsteps/concrete_00{0-4}.ogg                                                                                                   |
| plmove                            | walk_metal                                                                                                                                                                                                                                                    | footsteps/wood_00{0-4}.ogg                                                                                                       |
| plmove                            | walk_barefoot                                                                                                                                                                                                                                                 | footsteps/concrete_00{0-4}.ogg                                                                                                   |
| plmove                            | clear_obstacle                                                                                                                                                                                                                                                | footsteps/obstacle_00{0-1}.ogg                                                                                                   |
| fire_gun                          | brass_eject                                                                                                                                                                                                                                                   | impact/tin_medium_00{0-4}.ogg                                                                                                    |
| fire_gun                          | bio_lightning                                                                                                                                                                                                                                                 | digital/zap1-2/zapThreeToneDown/zapThreeToneUp/zapTwoTone-2.ogg                                                                  |
| fire_gun                          | bio_lightning_tail                                                                                                                                                                                                                                            | digital/laser1.ogg                                                                                                               |
| fire_gun                          | weapon_fire_suppressed                                                                                                                                                                                                                                        | synth_gunshot_pistol_crack.ogg, synth_gunshot_suppressed_thump.ogg (synth, no third-party samples; CC BY-SA 3.0 project default) |
| fire_gun / fire_gun_distant       | explicit ballistic weapon IDs (bounded set, 36 real current IDs)                                                                                                                                                                                              | real_fs128301_layered9.ogg / synth_gunshot_distant_echo.ogg (Xenonn CC0 / synth CC BY-SA 3.0, no third-party samples)            |
| reload                            | {weapon ids,default,start,end}                                                                                                                                                                                                                                | ui/click_00{1-5}.ogg, ui/toggle_00{1-4}.ogg                                                                                      |
| melee_swing                       | {small_bash,big_bash,small_cutting,big_cutting,default}                                                                                                                                                                                                       | impact/plank_medium/wood_heavy/wood_light/metal_heavy_00{0-4}.ogg                                                                |
| melee_hit_flesh / melee_hit_metal | {small_bash,big_bash,small_cutting,big_cutting,default}                                                                                                                                                                                                       | impact/punch_/glass_/metal_*_00{0-4}.ogg                                                                                         |
| bullet_hit                        | hit_flesh/hit_wall/hit_metal/hit_glass                                                                                                                                                                                                                        | impact/soft_medium/plate_medium/metal_medium/glass_light_00{0-4}.ogg                                                             |
| smash_success                     | smash_glass_contents                                                                                                                                                                                                                                          | impact/glass_light_00{0-4}.ogg                                                                                                   |
| smash_success                     | glass window, door, wall, roof and railing terrain ids (for example t_window, t_window_domestic, t_window_taped, t_door_glass__, t_wall_glass_, t_glass_roof, t_glass_railing, t_laminated__, t_ballistic__, t_reinforced__, t_tempered__, t_curtains, t_vat) | impact/glass_medium_00{0-4}.ogg                                                                                                  |
| smash_success                     | glass window-frame, skylight-frame, floor-light and ceiling-light ids (t_window_frame*, t_skylight_frame, t_thconc_floor_olight, f_olight*)                                                                                                                   | impact/glass_light_00{0-4}.ogg                                                                                                   |
| smash_success                     | glass furniture ids (f_bigmirror, f_displaycase*, f_glass_cabinet, f_vending*, f_aut_gas_console, f_cloning_vat*)                                                                                                                                             | impact/glass_medium_00{0-4}.ogg                                                                                                  |
| deal_damage                       | hurt_f/hurt_m                                                                                                                                                                                                                                                 | impact/punch_medium_00{0-4}.ogg                                                                                                  |
| mon_bite                          | bite_hit/bite_miss                                                                                                                                                                                                                                            | impact/glass_light_00{0-4}.ogg / ui/scratch_00{1-5}.ogg                                                                          |
| melee_attack                      | monster_melee_hit                                                                                                                                                                                                                                             | impact/punch_heavy_00{0-4}.ogg                                                                                                   |
| bionics                           | elec_discharge/acid_discharge/electrical variants/pixelated                                                                                                                                                                                                   | digital/zap*/laser1/glitch_00*.ogg                                                                                               |
| misc                              | timber                                                                                                                                                                                                                                                        | rpg/chop.ogg                                                                                                                     |
| menu_move                         | default                                                                                                                                                                                                                                                       | ui/select_00{1-8}.ogg                                                                                                            |
| menu_error                        | default                                                                                                                                                                                                                                                       | ui/error_00{1-8}.ogg                                                                                                             |
| vehicle                           | gear_shift                                                                                                                                                                                                                                                    | ui/click_00{1-5}.ogg                                                                                                             |
| vehicle_open / vehicle_close      | default                                                                                                                                                                                                                                                       | ui/open_/close_00{1-4}.ogg                                                                                                       |

Gunshots for ordinary ballistic weapons are added via explicit per-weapon variant mappings only (see `soundset.json`, the source of truth). No ballistic `default` entry exists, so unmatched guns fall back to `default` and stay silent in this pack; no ballistic sound is assigned to lasers/flamethrowers. Suppressed fire uses variant `weapon_fire_suppressed` only at the avatar (`fire_gun`). Existing `bio_lightning`/`bio_lightning_tail` digital bionics mappings are unchanged.

## Notes / gaps

- Audio format: Ogg Vorbis, 44100 Hz, mono, quality 4 (Kenney originals downmixed from stereo with
  ffmpeg; freesound originals resampled from 48 kHz mono and peak-normalized to the other clips).
- musicset.json is intentionally empty: no licensed background music is included.
- Glass breaking is mapped for the engine's real events: `smash_success` with the bashed object's
  terrain/furniture id (windows, glass doors, walls, floors and glass furniture), with
  `smash_glass_contents` for shattered loose items and glass weapons, and `bullet_hit`/`hit_glass`
  for thrown glass containers. `smash_success` deliberately has no `default` variant: the engine
  falls back to `default` when a variant is missing, which would make wood, metal, door and vehicle
  bashes play glass.
- Gaps (no CC0 source in the selected packs, or the event is not glass breaking): engine_start/engine_stop,
  vehicle part ids, plmove vehicle-part variants, fatigue_* breathing sounds, radio
  static/inaudible_chatter, weather sounds, explosions, non-glass bash/slash/smash, `smash_fail`,
  glass-shard trap sounds (`trap`/`glass*`), footstep legacy variants, player_laugh,
  tool/speech sounds, menu tab/scroll sounds.

## Gunshot additions (BN Overhaul HUD/fork)

| File                               | Source                                                                                                                                                 | Author            | License                        |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------- | ------------------------------ |
| real_fs128301_layered9.ogg         | Freesound "Layered Gunshot 9.wav" https://freesound.org/s/128301/ — preview derivative (HQ preview MP3 trimmed, converted to 44.1 kHz mono Ogg Vorbis) | Xenonn            | CC0 1.0                        |
| synth_gunshot_pistol_crack.ogg     | Original synthesis in `out/audio-audition/build_samples.py` (no third-party samples)                                                                   | Project-generated | CC BY-SA 3.0 (project default) |
| synth_gunshot_suppressed_thump.ogg | Original synthesis in `out/audio-audition/build_samples.py` (no third-party samples)                                                                   | Project-generated | CC BY-SA 3.0 (project default) |
| synth_gunshot_distant_echo.ogg     | Original synthesis in `out/audio-audition/build_samples.py` (no third-party samples)                                                                   | Project-generated | CC BY-SA 3.0 (project default) |

**Mapping:** `fire_gun` (near/standard) uses `real_fs128301_layered9.ogg`; `fire_gun_distant` uses `synth_gunshot_distant_echo.ogg` (same explicit IDs, see `soundset.json`). Suppressed uses variant `weapon_fire_suppressed` with synth pistol crack and suppressed thump at the avatar (`fire_gun`). No generic runtime default/wildcard ballistic fallback added.

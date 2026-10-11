# Overhaul Soundpack - Sources & Licenses

All audio files in this pack are taken from Kenney.nl asset packs and are released under **Creative Commons Zero (CC0)** —
free to use, modify, and redistribute without attribution (credit appreciated).

| Pack | Source | License |
|------|--------|---------|
| Impact Sounds 1.0 | http://kenney.nl/assets/impact-sounds | CC0 1.0 (http://creativecommons.org/publicdomain/zero/1.0/) |
| Digital Audio | http://kenney.nl/assets/digital-audio | CC0 1.0 |
| Interface Sounds 1.0 | http://kenney.nl/assets/interface-sounds | CC0 1.0 |
| RPG Audio | http://kenney.nl/assets/rpg-audio | CC0 1.0 |

Author: Kenney Vleugels (www.kenney.nl)
Creation dates: impact-sounds 2019-12-19; interface-sounds 2020-02-11; digital-audio/RPG-audio ~2019-2020.

## Sound effect mapping (id -> file set)

| id | variant | files |
|----|---------|-------|
| plmove | walk_grass | footsteps/grass_00{0-4}.ogg |
| plmove | walk_dirt | footsteps/carpet_00{0-4}.ogg |
| plmove | walk_tarmac | footsteps/concrete_00{0-4}.ogg |
| plmove | walk_metal | footsteps/wood_00{0-4}.ogg |
| plmove | walk_barefoot | footsteps/concrete_00{0-4}.ogg |
| plmove | clear_obstacle | ui/scratch_00{1-5}.ogg |
| fire_gun | brass_eject | impact/tin_medium_00{0-4}.ogg |
| fire_gun | bio_lightning | digital/zap1-2/zapThreeToneDown/zapThreeToneUp/zapTwoTone-2.ogg |
| fire_gun | bio_lightning_tail | digital/laser1.ogg |
| reload | {weapon ids,default,start,end} | ui/click_00{1-5}.ogg, ui/toggle_00{1-4}.ogg |
| melee_swing | {small_bash,big_bash,small_cutting,big_cutting,default} | impact/plank_medium/wood_heavy/wood_light/metal_heavy_00{0-4}.ogg |
| melee_hit_flesh / melee_hit_metal | {small_bash,big_bash,small_cutting,big_cutting,default} | impact/punch_/glass_/metal_*_00{0-4}.ogg |
| bullet_hit | hit_flesh/hit_wall/hit_metal | impact/soft_medium/plate_medium/metal_medium_00{0-4}.ogg |
| deal_damage | hurt_f/hurt_m | impact/punch_medium_00{0-4}.ogg |
| mon_bite | bite_hit/bite_miss | impact/glass_light_00{0-4}.ogg / ui/scratch_00{1-5}.ogg |
| melee_attack | monster_melee_hit | impact/punch_heavy_00{0-4}.ogg |
| bionics | elec_discharge/acid_discharge/electrical variants/pixelated | digital/zap*/laser1/glitch_00*.ogg |
| misc | timber | rpg/chop.ogg |
| menu_move | default | ui/select_00{1-8}.ogg |
| menu_error | default | ui/error_00{1-8}.ogg |
| vehicle | gear_shift | ui/click_00{1-5}.ogg |
| vehicle_open / vehicle_close | default | ui/open_/close_00{1-4}.ogg |

Gunshots, deaths and ambience are left to the engine's silence: the CC0 packs used here have no
recordings that sound like them, and a wrong sound is worse than none.

## Notes / gaps

- Audio format: Ogg Vorbis, 44100 Hz, mono, quality 4 (downmixed from the stereo originals with ffmpeg).
- musicset.json is intentionally empty: no licensed background music is included.
- Gaps (no CC0 source in the selected packs): engine_start/engine_stop, vehicle part ids, plmove
  vehicle-part variants, fatigue_* breathing sounds, radio static/inaudible_chatter, weather sounds,
  explosions, bash/slash/smash, footstep legacy variants, player_laugh, tool/trap/speech sounds,
  menu tab/scroll sounds.

# Known failures

Unit tests run per shard (see [AGENTS.md](../../AGENTS.md#test)). Catch2's `[!mayfail]` tag marks a known failure: the case still runs and reports what it sees, but a failure does not turn the shard red. So a red shard means a new failure, not one of the rows below.

Add a row when you tag a test and remove it when the test is fixed and the tag removed. `File` is the `file:line` of the `TEST_CASE`. `Owner` says where the tag came from: `upstream` means Cataclysm-BN introduced it before this fork's point, `fork` means this fork added it. `Since` is the date the tag, or the hidden test, appeared upstream. Symptom `unknown` means the file gives no reason and nothing was guessed.

## Known failing tests (`[!mayfail]`)

| Test | File | Tag | Symptom | Owner | Since |
| ---- | ---- | --- | ------- | ----- | ----- |
| filesystem_utf8_comp | `tests/filesystem_test.cpp:171` | `[filesystem] [!mayfail]` | Compares composed and decomposed UTF-8 paths; older macOS HFS+ decomposes file names, so lookups there differ (stated in the file comment). | upstream | 2021-02-05 |
| write_slope_to_speed_map_trig | `tests/monster_test.cpp:485` | `[.] [!mayfail]` | Writes out a slope-to-moves map for monster movement; also hidden `[.]`, so it never runs. No reason recorded for the `[!mayfail]` tag. | upstream | 2023-09-29 |
| write_slope_to_speed_map_square | `tests/monster_test.cpp:494` | `[.] [!mayfail]` | Square-distance variant of the slope map above; also hidden `[.]`, so it never runs. No reason recorded. | upstream | 2023-09-29 |
| monster_speed_square | `tests/monster_test.cpp:505` | `[speed] [.] [!mayfail]` | Characterization test for monster movement speed; also hidden `[.]`, so it never runs. No reason recorded. | upstream | 2023-09-29 |
| monster_speed_trig | `tests/monster_test.cpp:514` | `[speed] [.] [!mayfail]` | Monster speed with circular distance; file comment says it sometimes fails and looks RNG-dependent. Also hidden `[.]`. | upstream | 2023-09-29 |
| Aiming at a target partially covered by a wall | `tests/ranged_aiming_test.cpp:299` | `[.] [ranged] [aiming] [slow] [!mayfail]` | Whole TEST_CASE is commented out: "either the test is broken or it's a false positive"; the bundled Catch2 is too old for the SKIP() directive. | upstream | 2023-10-13 |
| unskilled_shooter_accuracy | `tests/ranged_balance_test.cpp:207` | `[ranged] [balance] [slow] [!mayfail]` | Unskilled shooter with an inaccurate pistol lands about 0.26 good hits where the case requires more than 0.5. | upstream | 2024-03-03 |
| all_nutrition_starve_test | `tests/stomach_contents_test.cpp:134` | `[!mayfail] [starve] [slow]` | Eight-day starvation check on stored nutrition; no reason recorded for the tag. | upstream | 2021-07-15 |
| sunlight and moonlight | `tests/sun_test.cpp:128` | `[sun] [sunlight] [moonlight] [!mayfail]` | Moonlight section requires a full moon at `season_length/6`, but with the default 14-day season the phase lands on a waxing gibbous (phase 3), and the sunlight numbers were written for 91-day seasons. Hidden upstream since 2020-10-02; re-tagged `[!mayfail]` by the fork so the case runs again. | fork | 2020-10-02 |
| avatar diving | `tests/water_movement_test.cpp:13` | `[diving] [!mayfail]` | Avatar diving in deep water; no reason recorded for the tag. | upstream | 2026-01-10 |

## Hidden tests (`[.]`)

These do not run in the sharded suite. They are listed so every tag in `tests/*.cpp` is accounted for; most are benchmarks, printers or slow calibration runs, not failures.

| Test | File | Tag | Reason hidden | Owner | Since |
| ---- | ---- | --- | ------------- | ----- | ----- |
| mo_plurals_calculation | `tests/cata_libintl_test.cpp:343` | `[libintl] [i18n] [.]` | Plural-form expression walker; hidden, reason not stated. | upstream | 2021-05-04 |
| gnu_transifex_rules_equal | `tests/cata_libintl_test.cpp:357` | `[libintl] [i18n] [.]` | Compares GNU and Transifex plural rules over 1,000,000 samples; hidden, reason not stated. | upstream | 2021-05-04 |
| bench_get_translated_string | `tests/cata_libintl_test.cpp:591` | `[libintl] [i18n] [benchmark] [.]` | Benchmark: string lookup in an MO file. | upstream | 2021-05-04 |
| bench_parse_mo | `tests/cata_libintl_test.cpp:615` | `[libintl] [i18n] [benchmark] [.]` | Benchmark: parse one MO file. | upstream | 2021-05-04 |
| bench_asssemble_trans_lib | `tests/cata_libintl_test.cpp:630` | `[libintl] [i18n] [benchmark] [.]` | Benchmark: parse an MO file and assemble a translation library. | upstream | 2021-05-04 |
| crafting_with_a_companion | `tests/crafting_test.cpp:247` | `[.]` | File comment: "This crashes subsequent testcases for some reason." | upstream | 2019-01-11 |
| grenade_lethality | `tests/explosion_balance_test.cpp:143` | `[.] [grenade] [explosion] [balance] [slow]` | Grenade lethality balance experiment; also `[slow]`. | upstream | 2020-06-18 |
| generic_factory_lookup_benchmark | `tests/generic_factory_test.cpp:186` | `[.] [generic_factory] [benchmark]` | Benchmark: single factory lookup. | upstream | 2021-06-15 |
| string_id_compare_benchmark | `tests/generic_factory_test.cpp:200` | `[.] [generic_factory] [string_id] [benchmark]` | Benchmark: `string_id` comparison. | upstream | 2021-06-15 |
| string_and_int_ids_benchmark | `tests/generic_factory_test.cpp:262` | `[.] [generic_factory] [int_id] [string_id] [benchmark]` | Benchmark: lookup performance of different flag containers. | upstream | 2023-10-05 |
| pavement_destroy | `tests/ground_destroy_test.cpp:21` | `[.]` | Pavement destroyed by pickaxe must not leave `t_flat_roof` (upstream issue #24707); hidden, reason not stated. | upstream | 2018-10-10 |
| explosion_on_ground | `tests/ground_destroy_test.cpp:44` | `[.]` | Ground explosion must not leave `t_flat_roof` (upstream issue #23250); hidden, reason not stated. | upstream | 2018-10-10 |
| explosion_on_floor_with_rock_floor_basement | `tests/ground_destroy_test.cpp:85` | `[.]` | Explosion on a floor with a rock-floor basement must create open air; hidden, reason not stated. | upstream | 2018-12-13 |
| collapse_checks | `tests/ground_destroy_test.cpp:136` | `[.]` | Roof collapse rules for removed floors and walls; hidden, reason not stated. | upstream | 2019-10-22 |
| scanned corpse bionic stack comparison benchmark | `tests/iuse_test.cpp:522` | `[.] [benchmark] [item] [bionic_scanner]` | Benchmark: bionic scanner on a corpse stack. | upstream | 2026-06-20 |
| active bionic scanner process_items benchmark near map items | `tests/iuse_test.cpp:545` | `[.] [benchmark] [item] [bionic_scanner]` | Benchmark: bionic scanner over nearby map items. | upstream | 2026-06-24 |
| translation_text_style_check | `tests/json_test.cpp:78` | `[json] [translation] [.]` | Diagnostic for the caret position in the text-style error message; the text style check itself lives in a clang-tidy lit test. | upstream | 2025-08-03 |
| translation_text_style_check_error_recovery | `tests/json_test.cpp:206` | `[json] [translation] [.]` | Error-recovery variant of the caret-position diagnostic above. | upstream | 2025-08-03 |
| line_to_performance | `tests/line_test.cpp:498` | `[.]` | Timing comparison of `line_to` over 10,000 points. | upstream | 2015-08-10 |
| make_static_macro_benchmark_string_id | `tests/make_static_test.cpp:32` | `[.] [make_static_macro] [benchmark]` | Benchmark: `STATIC` macro with `string_id`. | upstream | 2021-09-11 |
| mx_minefield real spawn | `tests/map_extra_test.cpp:23` | `[.] [map_extra] [overmap]` | Real overmap spawn search for minefields; hidden, reason not stated. | upstream | 2020-09-24 |
| lru_cache_perf | `tests/map_memory_test.cpp:74` | `[.]` | Performance measurement of `lru_cache`. | upstream | 2020-01-11 |
| Weak character using melee weapons against a brute | `tests/melee_balance_test.cpp:46` | `[.] [melee] [balance]` | Melee balance experiment: weak character versus a brute. | upstream | 2020-07-16 |
| Average character using melee weapons against a hulk | `tests/melee_balance_test.cpp:56` | `[.] [melee] [balance]` | Melee balance experiment: average character versus a hulk. | upstream | 2020-07-16 |
| Strong character using melee weapons against a kevlar zombie | `tests/melee_balance_test.cpp:66` | `[.] [melee] [balance]` | Melee balance experiment: strong character versus an armored zombie. | upstream | 2020-07-16 |
| Hulk smashing a character | `tests/melee_test.cpp:366` | `[.] [melee] [monattack]` | Melee probability balance experiment: hulk attacks. The tag string also contains a stray comma. | upstream | 2017-06-14 |
| monster_move_through_vehicle_holes | `tests/monster_test.cpp:522` | `[.] [monster]` | Monster pathing through holes in a vehicle; hidden, reason not stated. | upstream | 2025-05-09 |
| on_load-sane-values | `tests/npc_test.cpp:138` | `[.]` | Compares on-load NPC needs with per-turn accumulation; hidden, reason not stated. | upstream | 2017-06-07 |
| on_load-similar-to-per-turn | `tests/npc_test.cpp:195` | `[.]` | Compares on-load NPC needs with per-turn accumulation over long periods; hidden, reason not stated. | upstream | 2017-06-07 |
| npc_muscle_engine_broken_limbs | `tests/npc_vehicle_muscle_test.cpp:338` | `[.] [vehicle] [muscle] [npc] [injury]` | NPC muscle power with broken limbs; hidden, reason not stated. | upstream | 2026-03-26 |
| om_noise_layer_forest_export | `tests/overmap_noise_test.cpp:50` | `[.]` | Writes a raw `.pgm` dump of the forest noise layer. | upstream | 2019-05-13 |
| om_noise_layer_floodplain_export | `tests/overmap_noise_test.cpp:55` | `[.]` | Writes a raw `.pgm` dump of the floodplain noise layer. | upstream | 2019-05-13 |
| om_noise_layer_lake_export | `tests/overmap_noise_test.cpp:60` | `[.]` | Writes a raw `.pgm` dump of the lake noise layer. | upstream | 2019-05-13 |
| Brute force default batch generation to check for RNG bugs | `tests/overmap_test.cpp:388` | `[.] [overmap] [slow]` | Brute-force batch overmap generation to shake out RNG bugs; also `[slow]`. | upstream | 2020-08-24 |
| Find air temperatures for given body temperatures. | `tests/player_test.cpp:425` | `[.] [bodytemp]` | Prints the air-temperature table for a range of body temperatures; a calibration generator, not an assertion. | upstream | 2021-03-13 |
| Player body temperatures in water. | `tests/player_test.cpp:498` | `[.] [bodytemp]` | Compares converged body temperatures in water with expected values; hidden, reason not stated. | upstream | 2021-03-13 |
| Water hypothermia check. | `tests/player_test.cpp:556` | `[.] [bodytemp]` | Water hypothermia timing check; hidden, reason not stated. | upstream | 2021-03-13 |
| synthetic_range_test | `tests/ranged_balance_test.cpp:324` | `[.]` | File comment: finds inflection points but "I don't see any assertions we can make". | upstream | 2020-01-11 |
| roll_remainder_distribution | `tests/rng_test.cpp:23` | `[.]` | Distribution check for `roll_remainder` over many samples; hidden, reason not stated. | upstream | 2022-10-20 |
| x_in_y_distribution | `tests/rng_test.cpp:51` | `[.]` | Distribution check for `x_in_y` over many samples; hidden, reason not stated. | upstream | 2022-10-20 |
| cut_up_yields_all | `tests/salvage_test.cpp:116` | `[.]` | Runs `cut_up` over every item type; hidden, reason not stated. | upstream | 2025-05-16 |
| scent_matches_old | `tests/scent_test.cpp:144` | `[.]` | Characterization comparison against the old scent implementation; hidden, reason not stated. | upstream | 2022-08-18 |
| shadowcasting_runoff | `tests/shadowcasting_test.cpp:543` | `[.]` | File comment: "Some random edge cases aren't matching." | upstream | 2015-07-22 |
| shadowcasting_performance | `tests/shadowcasting_test.cpp:548` | `[.]` | Performance measurement of shadowcasting runoff. | upstream | 2015-08-10 |
| shadowcasting_3d_2d | `tests/shadowcasting_test.cpp:553` | `[.]` | Compares 3D and 2D shadowcasting; hidden, reason not stated. | upstream | 2015-09-25 |
| shadowcasting_3d_2d_performance | `tests/shadowcasting_test.cpp:558` | `[.]` | Performance measurement of 3D/2D shadowcasting. | upstream | 2015-09-25 |
| bresenham_vs_shadowcasting | `tests/shadowcasting_test.cpp:564` | `[.]` | File comment: "I'm not sure this will ever work." | upstream | 2015-08-10 |
| smart safe mode reach test with a horde | `tests/smart_features_benchmark_test.cpp:71` | `[.] [benchmark] [smart_safemode]` | Benchmark: smart safe-mode reach with a horde. | upstream | 2026-10-11 |
| monster info update with a horde in sight | `tests/smart_features_benchmark_test.cpp:107` | `[.] [benchmark] [smart_safemode]` | Benchmark: monster info update with a horde in sight. | upstream | 2026-10-11 |
| sizeof_new_id | `tests/string_ids_test.cpp:10` | `[.] [int_id] [string_id]` | Prints `sizeof` of id types; no assertions. | upstream | 2020-11-07 |
| translations_macro_char_address_translated | `tests/translations_test.cpp:96` | `[.] [translations] [i18n]` | Needs an `en_US` UTF-8 locale and the `en` `.mo` file; the case warns and returns when either is missing. | upstream | 2020-11-13 |
| crafting inventory rebuild benchmark near cargo-heavy vehicle | `tests/vehicle_cargo_perf_test.cpp:142` | `[.] [benchmark] [crafting] [vehicle]` | Benchmark: crafting inventory rebuild near a cargo-heavy vehicle. | upstream | 2026-06-17 |
| vehicle cargo recharge benchmark in item-heavy area | `tests/vehicle_cargo_perf_test.cpp:160` | `[.] [benchmark] [vehicle] [process_items]` | Benchmark: vehicle cargo recharge in an item-heavy area. | upstream | 2026-06-17 |
| vehicle idle benchmark with solar panels and storage batteries | `tests/vehicle_cargo_perf_test.cpp:182` | `[.] [benchmark] [vehicle] [solar]` | Benchmark: idle vehicle with solar panels and storage batteries. | upstream | 2026-06-17 |
| vehicle solar backfill benchmark with many storage batteries | `tests/vehicle_cargo_perf_test.cpp:200` | `[.] [benchmark] [vehicle] [solar]` | Benchmark: solar backfill with many storage batteries. | upstream | 2026-06-17 |
| vehicle_drag_calc_baseline | `tests/vehicle_drag_test.cpp:242` | `[.]` | File comment: generates C++ lines for the real drag test below. | upstream | 2020-01-11 |
| vehicle_find_efficiency | `tests/vehicle_efficiency_test.cpp:397` | `[.]` | File comment: not a test per se; prints the current vehicle efficiency state. | upstream | 2020-01-11 |
| make_vehicle_efficiency_case | `tests/vehicle_efficiency_test.cpp:404` | `[.]` | File comment: generates C++ lines for the real efficiency test below. | upstream | 2021-08-13 |
| check_vehicle_rotation_against_old | `tests/vehicle_test.cpp:565` | `[.]` | Compares vehicle rotation math against the old `tileray` algorithm; hidden, reason not stated. | upstream | 2022-08-18 |
| vehicle_turret | `tests/vehicle_turrets_test.cpp:60` | `[vehicle] [gun] [magazine] [.]` | Vehicle turret aiming over every turret type; hidden, reason not stated. | upstream | 2020-01-11 |
| vision_see_wall_in_moonlight | `tests/vision_test.cpp:497` | `[shadowcasting] [vision] [.]` | Checks moonlit vision; the same full-moon `CHECK` as `sun_test.cpp:128`, so it likely hits the 14-day-season phase mismatch. Hidden, reason not stated. | upstream | 2020-10-02 |
| weather realism | `tests/weather_test.cpp:237` | `[.]` | Compares simulated weather against NOAA climate data for New England; a statistical calibration. | upstream | 2020-10-02 |
| Wield time make cases | `tests/wield_times_test.cpp:100` | `[.]` | Make-cases mode of the wield-time test that prints a case table. | upstream | 2017-03-10 |

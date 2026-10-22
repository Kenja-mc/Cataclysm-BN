# CBN effective modern scheme — control lists

Method: base = data/raw/keybindings/{keybindings,messages,vehicle,edit_creature_effects}.json;
overlay = data/raw/control_schemes/modern.json, matched on (category, id), whole entry replaced
(src/input.cpp:314-319). Missing `category` => context `default` (src/input.cpp:233).
Keyboard-only; mouse/gamepad ignored for occupancy. Key comparison is case-sensitive:
"w" and "W" are different inputs (Shift is implied by the capital).

Counts: 124 unbound rows; 15 identical-key overload groups; 50 case-pair groups; 144 duplicated controls.

## 1. UNBOUND in modern (no keyboard binding)

Coverage: every category present in the effective scheme is listed. Categories with zero unbound
actions are named at the end of this section, not tabled.

Flags: `debug` = debug/dev tooling; `dev` = build/UI/system toggle normally reached from Options or
a manager screen; `menu` = same action id is bound with a keyboard key in another context, so the
capability is still reachable there.

### DEFAULTMODE (110)

| id | name | flag |
|---|---|---|
| wear | Wear Item | menu:INVENTORY_ITEM/INVENTORY/PICKUP |
| take_off | Take Off Worn Item | menu:INVENTORY_ITEM |
| eat | Eat | menu:INVENTORY_ITEM |
| read | Read | menu:INVENTORY_ITEM |
| wield | Wield | menu:INVENTORY_ITEM/INVENTORY |
| unload | Unload or Empty Wielded Item | menu:INVENTORY_ITEM |
| drop | Drop Item | menu:INVENTORY_ITEM |
| drop_adj | Drop Item to Adjacent Tile | menu:INVENTORY_ITEM |
| compare | Compare two Items | menu:LIST_ITEMS |
| sort_armor | Re-layer armor/clothing | menu:SORT_ARMOR |
| craft | Craft Items | menu:INVENTORY |
| missions | View Missions | menu:OVERMAP |
| item_action_menu | Item Action Menu | menu:ITEM_ACTIONS |
| control_vehicle | Control Vehicle | menu:VEH_INTERACT/VEHICLE |
| close | Close Door |  |
| smash | Smash Nearby Terrain |  |
| jump | Jump across an adjacent tile |  |
| pickup | Pick up items from one nearby tile |  |
| pickup_feet | Pickup Item(s) at Player Feet |  |
| open_consume | Consume Item Menu |  |
| quick_stack | Quick stack to nearby storage |  |
| sort_pile | Sort the pile you're standing on |  |
| attack | Attack in a direction |  |
| salvage | Salvage items |  |
| loot | Zone activities |  |
| look | Look Around |  |
| apply | Apply or Use Item |  |
| apply_wielded | Apply or Use Wielded Item |  |
| select_fire_mode | Toggle attack mode of Wielded Item |  |
| construct | Construct Terrain |  |
| open_wiki | Open Wiki |  |
| open_hhg | Open Hitchhiker's Guide |  |
| autoattack | Autoattack |  |
| peek | Peek Around Corners |  |
| fire_burst | Burst-Fire Wielded Item |  |
| long_craft | Craft as long as possible |  |
| player_data | View Player Info |  |
| chat | Chat with NPC |  |
| body_status | Body status |  |
| center | Center View |  |
| open | Open Door |  |
| advinv | Advanced Inventory management |  |
| grab | Grab something nearby |  |
| haul | Haul items along the ground |  |
| butcher | Butcher |  |
| listitems | List all items around the player |  |
| zones | Manage zones |  |
| organize | Swap Inventory Letters |  |
| pick_style | Select Martial Arts Style |  |
| select_default_ammo | Select default ammo for Wielded Item |  |
| bionics | View/Activate Bionics |  |
| mutations | View/Activate Mutations |  |
| recraft | Recraft last recipe |  |
| disassemble | Disassemble items |  |
| sleep | Sleep |  |
| auto_travel_mode | Toggle Auto Travel Mode |  |
| whitelist_enemy | Whitelist enemy |  |
| save | Save and Quit |  |
| factions | View Factions |  |
| scores | View Achievements, Scores, and Kills |  |
| morale | View Morale |  |
| messages | View Message Log |  |
| toggle_panel_adm | Sidebar Options |  |
| toggle_manual_combat_mode | Toggle manual combat mode |  |
| open_movement | Movement Mode Menu |  |
| cast_spell | Spellcasting |  |
| cast_last_spell | Cast Last Spell |  |
| diary | Open Diary |  |
| toggle_run | Toggle Run |  |
| toggle_crouch | Toggle Crouch |  |
| toggle_prone | Toggle Prone |  |
| reset_move | Reset Movement to Walk |  |
| toggle_map_memory | Toggle Map Memory | dev |
| reload_tileset | Reload Tileset | dev |
| toggle_sidebar_style | Switch Sidebar Style | dev |
| toggle_fullscreen | Toggle Fullscreen mode | dev |
| toggle_zone_overlay | Toggle Zone Overlay | dev |
| toggle_auto_features | Toggle Auto Features | dev |
| toggle_auto_pulp_butcher | Toggle Auto Pulp/Butcher | dev |
| toggle_auto_mining | Toggle Auto Mining | dev |
| toggle_auto_foraging | Toggle Auto Foraging | dev |
| toggle_auto_pickup | Toggle Auto Pickup | dev |
| autosafe | Toggle Auto-Safemode | dev |
| quicksave | Quicksave | dev |
| quickload | Quickload | dev |
| debug_mode | Toggle Debug Mode | debug |
| debug | Debug Menu | debug |
| lua_reload | Reload Lua Code | debug |
| debug_scent | View Scentmap | debug |
| debug_scent_type | View Scent Type | debug |
| debug_temp | View Temperature Map | debug |
| debug_visibility | View Visibility Map | debug |
| debug_lighting | View Lighting Map | debug |
| debug_radiation | View Radiation Map | debug |
| debug_submap_grid | View Submap Grid | debug |
| open_options | Options | menu:Options |
| open_autopickup | Autopickup manager | menu:Options |
| open_autonotes | Autonotes manager | menu:Options |
| open_safemode | Safe Mode manager | menu:Options |
| open_distraction_manager | Distractions manager | menu:Options |
| open_color | Color manager | menu:Options |
| open_world_mods | Active World Mods | menu:Options |
| toggle_thief_mode | Toggle thief mode | dev |
| SUICIDE | Commit Suicide |  |
| sky | Look at the sky |  |
| zoom_in | Zoom in | mouse:SCROLL_UP only |
| zoom_out | Zoom out | mouse:SCROLL_DOWN only |
| toggle_pixel_minimap | Toggle Minimap | dev |

### default (global context) (5)

| id | name | flag |
|---|---|---|
| SCROLL_UP | Scroll up | mouse only |
| SCROLL_DOWN | Scroll down | mouse only |
| SELECT | Select | mouse only |
| SEC_SELECT | Secondary Select | mouse only |
| MOUSE_MOVE | Mouse Move | mouse only |

### TARGET (1)

| id | name | flag |
|---|---|---|
| SELECT | Select target | mouse:MOUSE_RIGHT only |

### Panels (8)

| category | id | name | flag |
|---|---|---|---|
| UILIST | SCROLL_UP | Scroll up | mouse only |
| UILIST | SCROLL_DOWN | Scroll down | mouse only |
| MELEE_STYLE_PICKER | SCROLL_UP | Scroll up | mouse only |
| MELEE_STYLE_PICKER | SCROLL_DOWN | Scroll down | mouse only |
| ITEM_ACTIONS | SCROLL_UP | Scroll up | mouse only |
| ITEM_ACTIONS | SCROLL_DOWN | Scroll down | mouse only |
| ADVANCED_INVENTORY | ITEMS_DEFAULT | Restore default layout | dev |
| ADVANCED_INVENTORY | SAVE_DEFAULT | Save default layout | dev |

Categories with zero unbound actions: OVERMAP, INVENTORY, INVENTORY_ITEM, PICKUP, VEH_INTERACT,
VEHICLE, LOOK, CRAFTING, SPELL_SELECT, MESSAGE_LOG, DIARY, AUTO_NOTES, AUTO_PICKUP, SAFEMODE,
SORT_ARMOR, PANEL_MGMT, ZONES_MANAGER, CONSTRUCTION, BIONICS, MUTATIONS, HELP_KEYBINDINGS,
LIST_ITEMS, LIST_MONSTERS, NPC_TRADE, MODMANAGER_DIALOG, MAIN_MENU, OPTIONS, NEW_CHAR_*,
EDITMAP, EDITMAP_SHAPE, EDITMAP_FEATURE, OVERMAP_EDITOR, OVERMAP_NOTES, MINESWEEPER, SOKOBAN,
LIGHTSON, COLORS, CARAVAN, DEFENSE_SETUP, DIARY, LOAD_DELETE_CANCEL, LUA_CONSOLE, POPUP_WAIT,
STRING_INPUT, STRING_EDITOR, EXTENDED_DESCRIPTION, WORLDGEN_CONFIRM_DIALOG, YESNO, YESNOQUIT,
YES_NO_ALWAYS_NEVER, YN_IGNORE_QUERY, CANCEL_ACTIVITY_OR_IGNORE_QUERY, edit_creature_effects.

## 2. OVERLOADED

Contexts are the `category` field only (no global fallback), per the scheme model.

### 2a. Identical input string, two or more controls (15 groups)

| category | key | controls |
|---|---|---|
| default | `/` | FILTER, SEARCH |
| default | `f` | FILTER, TOGGLE_FAST_SCROLL |
| default | `UP` | UP, TEXT.UP |
| default | `DOWN` | DOWN, TEXT.DOWN |
| default | `LEFT` | LEFT, TEXT.LEFT |
| default | `RIGHT` | RIGHT, TEXT.RIGHT |
| default | `RETURN` | CONFIRM, TEXT.CONFIRM |
| default | `NUMPAD_6` | RIGHT, TEXT.CONFIRM |
| default | `TAB` | NEXT_TAB, EDITMAP_TAB |
| default | `ESC` | QUIT, TEXT.QUIT |
| default | `PPAGE` | PAGE_UP, LEVEL_UP, TEXT.PAGE_UP |
| default | `NPAGE` | PAGE_DOWN, LEVEL_DOWN, TEXT.PAGE_DOWN |
| INVENTORY_ITEM | `h` | WIELD, UNWIELD |
| INVENTORY_ITEM | `f` | FAVORITE_ADD, FAVORITE_REMOVE |
| VEHICLE | `f` | FOLD_VEHICLE, TOGGLE_FRIDGE |

### 2b. Case pairs in one context (one physical key + Shift) — 50 groups

| category | keys | controls |
|---|---|---|
| DEFAULTMODE | `w`/`W` | UP / shift_n (Look north) |
| DEFAULTMODE | `a`/`A` | LEFT / shift_w (Look west) |
| DEFAULTMODE | `s`/`S` | DOWN / shift_s (Look south) |
| DEFAULTMODE | `d`/`D` | RIGHT / shift_e (Look east) |
| DEFAULTMODE | `q`/`Q` | LEFTUP / shift_nw (Look northwest) |
| DEFAULTMODE | `e`/`E` | RIGHTUP / shift_ne (Look northeast) |
| DEFAULTMODE | `z`/`Z` | LEFTDOWN / shift_sw (Look southwest) |
| DEFAULTMODE | `c`/`C` | RIGHTDOWN / shift_se (Look southeast) |
| DEFAULTMODE | `x`/`X` | pause / cycle_move |
| INVENTORY_ITEM | `a`/`A` | LEFT (Cancel) / ACTIVATE |
| default | `h`/`H` | LEFT / LEFT_WIDE |
| default | `j`/`J` | DOWN / DOWN_WIDE |
| default | `k`/`K` | UP / UP_WIDE |
| default | `l`/`L` | RIGHT / RIGHT_WIDE |
| default | `s`/`S` | DOWN / SWAPTONPC |
| default | `w`/`W` | UP / CHOOSE_DESTINATION |
| default | `z`/`Z` | zoom_in / zoom_out |
| TARGET | `f`/`F` | FIRE / SWITCH_MODE |
| OVERMAP | `t`/`T` | PLACE_TERRAIN / TOGGLE_FOREST_TRAILS |
| PICKUP | `w`/`W` | UP / WEAR |
| VEH_INTERACT | `w`/`W` | UP / ASSIGN_CREW |
| VEH_INTERACT | `s`/`S` | DOWN / SIPHON |
| VEH_INTERACT | `a`/`A` | LEFT / RELABEL |
| VEH_INTERACT | `d`/`D` | RIGHT / UNLOAD |
| VEH_INTERACT | `e`/`E` | RIGHTUP / RENAME |
| VEH_INTERACT | `c`/`C` | RIGHTDOWN / TIRE_CHANGE |
| VEH_INTERACT | `z`/`Z` | LEFTDOWN / ZOOM_IN |
| ITEM_ACTIONS | `w`/`W` | UP / repair_metal |
| ITEM_ACTIONS | `s`/`S` | DOWN / repair_fabric |
| VEHICLE | `e`/`E` | TOGGLE_ENGINE / CONTROL_MANY_ELECTRONICS |
| VEHICLE | `c`/`C` | TOGGLE_CRUISE_CONTROL / TOGGLE_COOLER |
| VEHICLE | `z`/`Z` | TOGGLE_ALARM / TOGGLE_DOOR_LOCKS |
| VEHICLE | `b`/`B` | TOGGLE_WIDE_HEADLIGHT / TOGGLE_ATOMIC_LIGHT |
| VEHICLE | `h`/`H` | TOGGLE_HEADLIGHT / TOGGLE_REAPER |
| VEHICLE | `o`/`O` | TOGGLE_OVERHEAD_LIGHT / TOGGLE_HALF_OVERHEAD_LIGHT |
| VEHICLE | `k`/`K` | TOGGLE_REACTOR / TOGGLE_TRACKING |
| VEHICLE | `m`/`M` | TOGGLE_STEREO / TOGGLE_CAMERA |
| VEHICLE | `p`/`P` | TOGGLE_WATER_PURIFIER / TOGGLE_PLANTER |
| VEHICLE | `r`/`R` | TOGGLE_FREEZER / TOGGLE_SCOOP |
| VEHICLE | `l`/`L` | RELEASE_CONTROLS / TOGGLE_AISLE_LIGHT |
| VEHICLE | `v`/`V` | TURRET_ALL_OVERRIDE / TURRET_MANUAL_OVERRIDE |
| VEHICLE | `x`/`X` | TURRET_FIRE_MODE / TURRET_MANUAL_AIM |
| VEHICLE | `t`/`T` | TURRET_TARGET_MODE / TURRET_SINGLE_FIRE |
| ADVANCED_INVENTORY | `m`/`M` | MOVE_VARIABLE_ITEM / MOVE_ITEM_STACK |
| ADVANCED_INVENTORY | `t`/`T` | CATEGORY_SELECTION / TOGGLE_FILTER_AUTORESET |
| LOOK | `v`/`V` | EXTENDED_DESCRIPTION / LIST_ITEMS |
| CRAFTING | `v`/`V` | TOGGLE_RECIPE_UNREAD / MARK_ALL_RECIPES_READ |
| SORT_ARMOR | `e`/`E` | EQUIP_ARMOR / EQUIP_ARMOR_HERE |
| OPTIONS | `r`/`R` | RESET_OPTION / RESET_PAGE |

### 2c. Supplementary: cross-context collisions that become live at runtime

`src/input.cpp:588-619` falls back to the `default` context, so these are real in-game collisions but
not same-category ones. Listed for the three play contexts only.

| context | key | category holder | global holder |
|---|---|---|---|
| DEFAULTMODE | `f` | fire | FILTER, TOGGLE_FAST_SCROLL |
| DEFAULTMODE | `q` / `Q` | LEFTUP / shift_nw | QUIT |
| DEFAULTMODE | `ESC` | main_menu | QUIT, TEXT.QUIT |
| DEFAULTMODE | `RETURN` | action_menu | CONFIRM, TEXT.CONFIRM |
| DEFAULTMODE | `TAB` | NEXT_TARGET | NEXT_TAB, EDITMAP_TAB |
| DEFAULTMODE | `BACKTAB` | PREV_TARGET | PREV_TAB |
| DEFAULTMODE | `PPAGE` / `NPAGE` | — | PAGE_UP/DOWN, TEXT.PAGE_UP/DOWN |
| DEFAULTMODE | `r` / `R` | reload_item | RESET_FILTER |
| TARGET | `f` / `F` | FIRE / SWITCH_MODE | FILTER |
| TARGET | `RETURN` | FIRE | CONFIRM |
| TARGET | `q` | LEFTUP | QUIT |
| TARGET | `PPAGE` / `NPAGE` | PREV_TARGET / NEXT_TARGET | PAGE_UP / PAGE_DOWN |
…
| NEW_CHAR_TRAITS | TOGGLE_CHARACTER_PREVIEW_CLOTHES | c, C |

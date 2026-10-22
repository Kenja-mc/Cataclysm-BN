# Options

## Option Group

Adds a new group to the options menu

| Key   | Description                                                                         |
| ----- | ----------------------------------------------------------------------------------- |
| type  | Always `OPTION_GROUP`                                                               |
| id    | id of the group                                                                     |
| page  | `general` `interface` `graphics` `performance` `world_default` `debug` or `android` |
| title | Visible Option Name                                                                 |
| desc  | Extended option description                                                         |

## Option Space

Adds a new space to the options menu

| Key  | Description                                                                         |
| ---- | ----------------------------------------------------------------------------------- |
| type | Always `OPTION_SPACE`                                                               |
| page | `general` `interface` `graphics` `performance` `world_default` `debug` or `android` |

## Option

Adds an option to the options menu

| Key             | Description                                                                                                                                                 |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| type            | Always `OPTION`                                                                                                                                             |
| id              | Unique option id                                                                                                                                            |
| stype           | Type of option                                                                                                                                              |
| page            | `general` `interface` `graphics` `performance` `world_default` `debug` or `android`                                                                         |
| group           | Optional group id it is under                                                                                                                               |
| menu_text       | Text displayed for option value                                                                                                                             |
| tooltip         | Extra info displayed for option                                                                                                                             |
| default         | Default value                                                                                                                                               |
| default_android | Default value on android                                                                                                                                    |
| min             | minimum value for integers / floats                                                                                                                         |
| max             | Maximum value for integers / floats                                                                                                                         |
| step            | Step for floats in menu                                                                                                                                     |
| hide            | Hides with `none`, `always`, `sdl_hide` ( with sdl ), `curses_hide` ( with curses ), `no_sound_hide` ( without sound ), `android_only` ( when not android ) |
| deps            | Array of `option` ( other option id ) and `values` ( valid option values ) to use the config                                                                |

## World Preset

Adds a named set of world option values that the player can apply from the world options page.

| Key         | Description                                                              |
| ----------- | ------------------------------------------------------------------------ |
| type        | Always `WORLD_PRESET`                                                    |
| id          | Unique preset id                                                         |
| name        | Visible preset name                                                      |
| description | Shown next to the name in the preset picker                              |
| values      | Object of option id to value; values are strings, numbers or booleans    |

Presets are offered where a concrete world is edited: while the world is created, and in game on
the Current world page. Applying one resets the world options page to its built-in defaults first,
then sets the listed options, so a preset always produces the same world settings.

Every entry is checked after all option definition files load. A preset that names an unknown
option, an option outside the `world_default` page, a hidden option, or a value the option does
not accept is dropped with a debug message.

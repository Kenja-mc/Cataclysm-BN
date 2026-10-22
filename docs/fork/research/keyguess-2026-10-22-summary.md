# Key-guess survey

Models: jev-latest, gpt-6-luna-decisions. Trials per model and scenario: 3.

| Scenario | Model | Key | Confidence | Result | Evidence |
|---|---|---|---|---|---|
| inventory | jev-latest | `i` | 0.84 | reached | inventory list |
| inventory | jev-latest | `i` | 0.87 | reached | inventory list |
| inventory | jev-latest | `i` | 0.83 | reached | inventory list |
| inventory | gpt-6-luna-decisions | `i` | 0.94 | reached | inventory list |
| inventory | gpt-6-luna-decisions | `i` | 0.90 | reached | inventory list |
| inventory | gpt-6-luna-decisions | `i` | 0.84 | reached | inventory list |
| map | jev-latest | `m` | 0.47 | reached | map screen |
| map | jev-latest | `m` | 0.45 | reached | map screen |
| map | jev-latest | `m` | 0.44 | reached | map screen |
| map | gpt-6-luna-decisions | `M` | 0.71 | missed | map screen |
| map | gpt-6-luna-decisions | `M` | 0.77 | missed | map screen |
| map | gpt-6-luna-decisions | `M` | 0.92 | missed | map screen |
| wait | jev-latest | `.` | 0.69 | missed | position held, clock (1324800, -100) -> (1324800, -100) |
| wait | jev-latest | `.` | 0.68 | missed | position held, clock (1324800, -100) -> (1324800, -100) |
| wait | jev-latest | `.` | 0.65 | missed | position held, clock (1324800, -100) -> (1324800, -100) |
| wait | gpt-6-luna-decisions | `Space` | 0.46 | missed | position held, clock (1324800, -100) -> (1324800, -100) |
| wait | gpt-6-luna-decisions | `5` | 0.23 | missed | position held, clock (1324800, -100) -> (1324800, -100) |
| wait | gpt-6-luna-decisions | `Space` | 0.59 | missed | position held, clock (1324800, -100) -> (1324800, -100) |
| hub | jev-latest | `m` | 0.35 | missed | action hub |
| hub | jev-latest | `m` | 0.33 | missed | action hub |
| hub | jev-latest | `m` | 0.35 | missed | action hub |
| hub | gpt-6-luna-decisions | `?` | 0.51 | missed | action hub |
| hub | gpt-6-luna-decisions | `?` | 0.63 | missed | action hub |
| hub | gpt-6-luna-decisions | `?` | 0.54 | missed | action hub |
| hub_craft | jev-latest | `6` | 0.64 | first step | recipe list |
| hub_craft | jev-latest | `6` | 0.77 | first step | recipe list |
| hub_craft | jev-latest | `6` | 0.63 | first step | recipe list |
| hub_craft | gpt-6-luna-decisions | `6` | 0.95 | first step | recipe list |
| hub_craft | gpt-6-luna-decisions | `6` | 0.96 | first step | recipe list |
| hub_craft | gpt-6-luna-decisions | `6` | 0.90 | first step | recipe list |
| wield | jev-latest | `w` | 0.23 | missed | wielded item: fists |
| wield | jev-latest | `u` | 0.22 | missed | wielded item: fists |
| wield | jev-latest | `u` | 0.22 | missed | wielded item: fists |
| wield | gpt-6-luna-decisions | `w` | 0.52 | missed | wielded item: fists |
| wield | gpt-6-luna-decisions | `Enter` | 0.30 | missed | wielded item: fists |
| wield | gpt-6-luna-decisions | `w` | 0.62 | missed | wielded item: fists |
| inspect_armor | jev-latest | `Enter` | 0.90 | reached | item menu |
| inspect_armor | jev-latest | `Enter` | 0.95 | reached | item menu |
| inspect_armor | jev-latest | `Enter` | 0.81 | reached | item menu |
| inspect_armor | gpt-6-luna-decisions | `Enter` | 0.45 | reached | item menu |
| inspect_armor | gpt-6-luna-decisions | `Enter` | 0.89 | reached | item menu |
| inspect_armor | gpt-6-luna-decisions | `Enter` | 0.51 | reached | item menu |

Goals reached: 15/42 answered; 0 model errors.
Hint text visible in captures: none.

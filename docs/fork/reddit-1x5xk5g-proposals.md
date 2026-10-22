# Community proposals: the difficulty thread

Source: [Does anyone else feel the same way?](https://www.reddit.com/r/cataclysmbn/comments/1x5xk5g/does_anyone_else_feel_the_same_way/), r/cataclysmbn, posted 2026-10-14.
First read on 2026-10-16 (25 comments). Read again on 2026-10-21 through the authenticated
reddit-fetch tool: 40 comments, post score 21. The poster is u/Dryym.

## In one screen

The poster likes Bright Nights. He says it is fun, but it gets easy too fast with default settings.
Most replies agree, and most tell him to change the world settings and use mods.
Several replies say his run was lucky. The best-scoring critical reply says that vehicles and the
open world are the real cause, and that number changes only add waiting.
The top comment (25 points) says Bright Nights is fun but less "compelling" than Dark Days Ahead.

## What changed since the first read

- A Bright Nights developer (u/Aurrora) answered. He agrees that some Dark Days Ahead systems could
  come back as world options, and he says a **fluid grid** was merged into the nightly build, to be
  developed further.
- The poster listed what he misses: pockets, proficiencies, theory versus practice skill, cable
  grids that the player builds, the body graph, and some mod features.
- The poster says the evacuation shelter grid comes ready-made, so his first fridge did not feel
  earned.
- New replies: vehicles "destroy balance" (u/TooFewSecrets), one moose gives hundreds of sausages,
  skill rust exists as an option that players do not find (u/Proxiehunter), and Dark Days Ahead
  players are confused by dropping a backpack and the different examine menu (u/MandatoryDebuff).

## Difficulty and world settings

- Lower the loot. Use 0.80x global loot, and 0.65x for guns and ammo. (Crusader_Exodus, 6 points)
- Raise monster health and damage a little. Stop below about +20% damage, because turrets and robots
  become unfair. (Crusader_Exodus)
- Use the "cars to wrecks" mod, so the midgame does not become a deathmobile run. (Crusader_Exodus)
- Slow experience gain to 0.02x and double monster health. (Ecstatic_Judge_4515, 2)
- Turn down vehicle condition and frequency, turn up monster health and density. (MandatoryDebuff)
- Add ready-made world presets. The settings exist, but they are long and a player cannot see what
  each setting does. (CV514)

## Gameplay and design

- Add tradeoffs and scarce resources, not only tougher enemies. (Xemxah, 11)
- Vehicles and the open world trivialize survival. (Xemxah, TooFewSecrets)
- Bring back waves of enemies and base defense. (Ardashasaur, 3)
- Use the Dark Days Ahead split of practical and theory skill. (Fl414r, the poster)

## Interface and small quality of life

- Split a pill stack with the `m` key instead of using pockets. (Proxiehunter, 9)
- Make existing options easier to find, for example skill rust. (Proxiehunter)

## Scope for this fork

The fork keeps the Bright Nights rules and changes only the interface, the controls and duplicate
item data. By that rule:

- **World presets fit the fork.** They only fill in existing world options, so the player still
  sees and can change every value. Implemented on 2026-10-21 (`p` on the world options page; see
  `OVERHAUL.md`). The Scarce preset uses the thread's 0.80x loot and 0.65x guns and ammo values.
- **Fluid grids** are an upstream system. The fork made them explain refused connections, partial
  fills and the water purity rule, without changing what they can do.
- Balance changes (loot, damage, skill speed, vehicles) stay out of the fork's defaults. The presets
  make them one choice away instead.
- Pockets, proficiencies and theory skill are engine features that upstream would have to decide.

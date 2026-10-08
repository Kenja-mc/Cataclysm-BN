# Limited_Reviving_Zombies

A mod inspired by `No_Reviving` (which bans revival entirely) that **limits revival instead of banning it**.
Zombies still get back up as before, but they come back weaker and slower depending on how damaged the corpse is, and they can't keep rising again and again.
It only affects monsters whose **species is ZOMBIE**. Other things that "revive", such as self-repairing robots, are left alone.

This mod (including its documentation) was made largely with the help of Claude Opus.
Tested on stable v0.12 and experimental v260922.

---

## 1. Background: what the base game already does

This matters for understanding the mod, so here is how the base game works first.
The game **already** makes more damaged corpses revive later and weaker.
However, `REVIVES_HEALTHY` undoes that, and once you kill a weakened zombie,
its corpse can rise again from scratch.

## 2. What this mod adds

1. **Disables `REVIVES_HEALTHY`** (in JSON, via `monster_adjustment`)
   → No zombie rises at full strength anymore, so the game's own weakening always applies.
2. **A cap on HP when reviving**, by damage level (undamaged 65% → mangled 25%).
   If the game's own result is lower, that wins, so this **only ever makes them weaker**.
3. **A helpless moment right after rising.** Depending on damage, they are downed and stunned for 5–30 seconds.
   This gives you time to smash their head while they are still struggling to get up.
4. **Rigor mortis** (this mod's own effect, `lrz_rigor`). For 2–12 minutes, their speed drops by 10–40.
5. **A limit on how many times they can revive** (1 by default). When you kill a revived zombie, its corpse
   is treated as `PULPED` and never rises again. If you can see it, you get the message "The ... is too broken to rise again."

### Values by damage level (defaults)

| Corpse damage | HP cap on revival | Helpless time | Rigor mortis | Speed penalty |
|---|---|---|---|---|
| 0 (undamaged) | 65% of max | 5 seconds | 2 minutes | -10 |
| 1 | 50% | 12 seconds | 5 minutes | -20 |
| 2 | 35% | 20 seconds | 8 minutes | -30 |
| 3 (mangled) | 25% | 30 seconds | 12 minutes | -40 |

The game's own revival delay (about 6–24 hours) is unchanged,
so "the more damaged, the slower it revives" still comes from the base game.

## 3. Changing the settings

Just edit `mod.cfg` at the top of `main.lua`.

```lua
mod.cfg = {
  max_revivals = 1,   -- how many times the same corpse can rise (0 behaves like a no-revival mod)
  hp_ratio  = { [0] = 0.65, [1] = 0.50, [2] = 0.35, [3] = 0.25 },
  rise_secs = { [0] = 5,    [1] = 12,   [2] = 20,   [3] = 30 },
  rigor_mins= { [0] = 2,    [1] = 5,    [2] = 8,    [3] = 12 },
  announce  = true,   -- message when a corpse goes quiet for good
  debug     = false,  -- write details to the debug log
}
```

`main.lua` supports hot reload. Edit the file while playing and run
**Reload Lua Code** from the debug menu to apply the change right away.
Only the size of the speed penalty lives in `effects.json` (`speed_mod`), so changing it needs a world reload.

## 4. Installation and notes

- Put the whole folder in `data/mods/` or in `mods/` in your user directory.
- **Requires a Lua-enabled build** (`lua_api_version: 2`). The official Windows release supports it.
  Enabling it on a build without Lua causes an error when the mod loads.
- **Don't use it together with** `No_Reviving` (the no-revival mod). That mod removes `REVIVES`, leaving nothing for this one to do.
- You can add it to an existing world. However, corpses already on the map have no record of how many times they have revived, so the first revival after adding the mod happens normally.
- Zombies you revive yourself as zombie slaves (zlaves) are not affected.

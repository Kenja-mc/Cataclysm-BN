gdebug.log_info("LRZ: preload.")

local mod = game.mod_runtime[game.current_mod]

game.add_hook("on_monster_spawn", function(...)
  if mod.on_monster_spawn then return mod.on_monster_spawn(...) end
end)

game.add_hook("on_mon_death", function(...)
  if mod.on_mon_death then return mod.on_mon_death(...) end
end)

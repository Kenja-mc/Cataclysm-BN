--[[
  Limited Zombie Revival - preload.lua

  フックの登録だけを行う。実装は main.lua 側（hot-reload できるように）。
  game.add_hook はこの時点で呼ぶ必要があるが、実体は呼び出し時に
  mod テーブルから取り出されるので、main.lua を書き換えて
  「Reload Lua Code」するだけで挙動を差し替えられる。

  Assisted-by: Claude:claude-opus-5-5
]]

gdebug.log_info("LRZ: preload.")

local mod = game.mod_runtime[game.current_mod]

-- 死体から蘇ったモンスターを捕まえる（revive_corpse() 内で呼ばれる）
game.add_hook("on_monster_spawn", function(...)
  if mod.on_monster_spawn then
    return mod.on_monster_spawn(...)
  end
end)

-- 蘇った個体が再び倒れたとき、その死体に「もう起き上がれない」印を付ける
game.add_hook("on_mon_death", function(...)
  if mod.on_mon_death then
    return mod.on_mon_death(...)
  end
end)

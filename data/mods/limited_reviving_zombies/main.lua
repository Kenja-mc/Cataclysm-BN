gdebug.log_info("LRZ: main.")

local mod = game.mod_runtime[game.current_mod]

mod.cfg = {
  max_revivals = 1,

  hp_ratio = { [0] = 0.65, [1] = 0.50, [2] = 0.35, [3] = 0.25 },

  rise_secs = { [0] = 5, [1] = 12, [2] = 20, [3] = 30 },

  rigor_mins = { [0] = 2, [1] = 5, [2] = 8, [3] = 12 },

  announce = true,

  debug = false,
}

local SPECIES_ZOMBIE = SpeciesTypeId.new("ZOMBIE")
local EFF_DOWNED = EffectTypeId.new("downed")
local EFF_STUNNED = EffectTypeId.new("stunned")
local EFF_RIGOR = EffectTypeId.new("lrz_rigor")
local EFF_PET = EffectTypeId.new("pet")
local EFF_PACIFIED = EffectTypeId.new("pacified")
local FLAG_PULPED = JsonFlagId.new("PULPED")

local VAR_GEN = "lrz_gen"

local function log(fmt, ...)
  if mod.cfg.debug then gdebug.log_info("LRZ: " .. string.format(fmt, ...)) end
end

local function clamp_dl(dl)
  if not dl or dl < 0 then
    return 0
  elseif dl > 3 then
    return 3
  end
  return dl
end

local function find_corpse_at(pos, mtype_str, prefer_marked)
  local map = gapi.get_map()
  if not map then return nil end
  local stack = map:get_items_at(pos)
  if not stack then return nil end
  local fallback = nil
  for _, it in pairs(stack) do
    if it and it:is_corpse() and not it:has_flag(FLAG_PULPED) then
      local mt = it:get_mtype()
      if mt and mt:str() == mtype_str then
        local marked = it:get_var_num(VAR_GEN, 0) > 0
        if marked == prefer_marked then return it end
        fallback = fallback or it
      end
    end
  end
  return fallback
end

local function guess_dl_from_hp(mon)
  local hp_max = mon:get_hp_max()
  if not hp_max or hp_max <= 0 then return 0 end
  local r = mon:get_hp() / hp_max
  if r >= 0.6 then
    return 0
  elseif r >= 0.3 then
    return 1
  elseif r >= 0.2 then
    return 2
  end
  return 3
end

local function add_effect_safe(mon, eff, dur, intensity)
  if intensity then
    local ok = pcall(function() mon:add_effect(eff, dur, nil, intensity) end)
    if ok then return end
  end
  pcall(function() mon:add_effect(eff, dur) end)
end

local function handle_revived(mon)
  if not mon:has_effect(EFF_DOWNED) then return end
  if not mon:has_flag(MonsterFlag.REVIVES) then return end
  if not mon:in_species(SPECIES_ZOMBIE) then return end
  if mon:has_effect(EFF_PET) or mon:has_effect(EFF_PACIFIED) then return end

  local pos = mon:get_pos_ms()
  local corpse = find_corpse_at(pos, mon:get_type():str(), true)

  local dl, gen
  if corpse then
    dl = clamp_dl(corpse:get_damage_level())
    gen = math.floor(corpse:get_var_num(VAR_GEN, 0))
  else
    dl = guess_dl_from_hp(mon)
    gen = 0
  end

  local ratio = mod.cfg.hp_ratio[dl] or 0.5
  local hp_max = mon:get_hp_max()
  local target = math.floor(hp_max * ratio)
  if target < 1 then target = 1 end
  local cur = mon:get_hp()
  if target < cur then mon:set_hp(target) end

  local secs = mod.cfg.rise_secs[dl]
  if secs and secs > 0 then
    local dur = TimeDuration.from_seconds(secs)
    add_effect_safe(mon, EFF_DOWNED, dur)
    add_effect_safe(mon, EFF_STUNNED, dur)
  end

  local mins = mod.cfg.rigor_mins[dl]
  if mins and mins > 0 then add_effect_safe(mon, EFF_RIGOR, TimeDuration.from_minutes(mins), dl + 1) end

  mon:set_value(VAR_GEN, tostring(gen + 1))

  log("revived %s: dl=%d gen=%d hp=%d/%d", mon:get_name(), dl, gen + 1, mon:get_hp(), hp_max)
end

mod.on_monster_spawn = function(params)
  local mon = params and params.monster
  if not mon then return end
  local ok, err = pcall(handle_revived, mon)
  if not ok then gdebug.log_info("LRZ: on_monster_spawn failed: " .. tostring(err)) end
end

local function handle_death(mon)
  if not mon:has_flag(MonsterFlag.REVIVES) then return end
  if not mon:in_species(SPECIES_ZOMBIE) then return end

  local gen = tonumber(mon:get_value(VAR_GEN)) or 0
  if gen < 1 and mod.cfg.max_revivals > 0 then
    return
  end

  local pos = mon:get_pos_ms()
  local corpse = find_corpse_at(pos, mon:get_type():str(), false)
  if not corpse then return end

  corpse:set_var_num(VAR_GEN, gen)

  if gen >= mod.cfg.max_revivals then
    corpse:set_flag(FLAG_PULPED)
    log("corpse of %s sealed (gen=%d)", mon:get_name(), gen)
    if mod.cfg.announce then
      local u = gapi.get_avatar()
      if u and u:sees(pos) then
        gapi.add_msg(MsgType.good, string.format(locale.gettext("The %s is too broken to rise again."), mon:get_name()))
      end
    end
  end
end

mod.on_mon_death = function(params)
  if not params then return end
  local mon = params.mon or params.creature
  if not mon then return end
  local as_mon = nil
  pcall(function() as_mon = mon:as_monster() end)
  if as_mon then mon = as_mon end
  local ok, err = pcall(handle_death, mon)
  if not ok then gdebug.log_info("LRZ: on_mon_death failed: " .. tostring(err)) end
end

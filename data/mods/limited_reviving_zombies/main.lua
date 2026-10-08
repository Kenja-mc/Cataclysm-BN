--[[
  Limited Zombie Revival - main.lua

  ゾンビの復活を「禁止」ではなく「制限」する。

  本体(BN)の仕様おさらい:
    * 死体は MF_REVIVES を持つ種族のものだけが起き上がる
    * 起き上がるまでの時間は item::ready_to_revive() で決まり、
      「経過時間 ÷ (損壊度+1)」が 6 時間を超えてから抽選が始まる
      → 無傷の死体は死後約6時間、損壊した死体は12〜24時間かかる
    * 復活時のHPと速度は monster::init_from_item() で
      HP×0.7, 速度×0.8 され、さらに (損壊度+1) で割られる
    * ただし MF_REVIVES_HEALTHY を持つ種族は、この減衰を全部無視して
      「最大HP・最大速度」で起き上がる

  このMODが足すもの:
    1. REVIVES_HEALTHY を種族単位で無効化（JSON側）
       → 万全の状態で起き上がるゾンビが居なくなる
    2. 復活時HPを損壊度に応じた上限まで引き下げる（本体より低い時はそのまま）
    3. 起き上がった直後、損壊度に応じた時間だけ無力になる（downed + stunned）
    4. しばらく「死後硬直」で移動速度が落ちる（effects.json の lrz_rigor）
    5. 同じ死体が起き上がれる回数に上限を設ける
       → 上限に達した死体は PULPED 扱いになり、二度と動かない

  数値はすべて下の mod.cfg で変更できる。変更後は
  デバッグメニューの「Reload Lua Code」で即反映される。

  Assisted-by: Claude:claude-opus-5-5
]]

gdebug.log_info("LRZ: main.")

local mod = game.mod_runtime[game.current_mod]

----------------------------------------------------------------------
-- 設定
----------------------------------------------------------------------

mod.cfg = {
  -- 同じ死体が起き上がれる回数。
  --   1 = 一度だけ復活できる（その個体を倒せば、その死体はもう動かない）
  --   2 = 二度まで復活できる  /  0 = 復活そのものを禁止
  max_revivals = 1,

  -- 復活時HP（最大HPに対する割合）。添字は死体の損壊度 0(無傷)〜3(ボロボロ)。
  -- 本体の計算結果のほうが低い場合は、そちらが優先される（＝弱くする方向にしか働かない）。
  hp_ratio = { [0] = 0.65, [1] = 0.50, [2] = 0.35, [3] = 0.25 },

  -- 起き上がった直後、倒れた/朦朧とした状態で無力になる秒数。
  rise_secs = { [0] = 5, [1] = 12, [2] = 20, [3] = 30 },

  -- 「死後硬直」(lrz_rigor) の持続時間（分）。強度は損壊度+1で、
  -- 1段階につき移動速度 -10。
  rigor_mins = { [0] = 2, [1] = 5, [2] = 8, [3] = 12 },

  -- 死体が二度と起き上がらなくなったとき、見えていればメッセージを出す
  announce = true,

  -- 詳細をデバッグログに出す
  debug = false,
}

----------------------------------------------------------------------
-- 定数
----------------------------------------------------------------------

local SPECIES_ZOMBIE = SpeciesTypeId.new("ZOMBIE")
local EFF_DOWNED = EffectTypeId.new("downed")
local EFF_STUNNED = EffectTypeId.new("stunned")
local EFF_RIGOR = EffectTypeId.new("lrz_rigor")
local EFF_PET = EffectTypeId.new("pet")
local EFF_PACIFIED = EffectTypeId.new("pacified")
local FLAG_PULPED = JsonFlagId.new("PULPED")

-- 死体・モンスターに刻む「何度目の復活か」
local VAR_GEN = "lrz_gen"

----------------------------------------------------------------------
-- 補助関数
----------------------------------------------------------------------

local function log(fmt, ...)
  if mod.cfg.debug then
    gdebug.log_info("LRZ: " .. string.format(fmt, ...))
  end
end

-- 損壊度を 0〜3 に丸める（4 = 完全に破壊された死体は復活しないので来ない）
local function clamp_dl(dl)
  if not dl or dl < 0 then
    return 0
  elseif dl > 3 then
    return 3
  end
  return dl
end

-- 指定地点にある、そのモンスター種の死体を探す。
-- 復活処理(item::process_corpse)は revive_corpse() の直後に死体を消すので、
-- on_monster_spawn の時点ではまだ足元に死体が残っている。
--   prefer_marked = true  … 復活時。世代が刻まれた死体（＝2回目以降）を優先。
--   prefer_marked = false … 死亡時。まだ何も刻まれていない「今落ちた死体」を優先。
-- どちらの場合も、既に封じた(PULPED)死体は無視する。
local function find_corpse_at(pos, mtype_str, prefer_marked)
  local map = gapi.get_map()
  if not map then
    return nil
  end
  local stack = map:get_items_at(pos)
  if not stack then
    return nil
  end
  local fallback = nil
  for _, it in pairs(stack) do
    if it and it:is_corpse() and not it:has_flag(FLAG_PULPED) then
      local mt = it:get_mtype()
      if mt and mt:str() == mtype_str then
        local marked = it:get_var_num(VAR_GEN, 0) > 0
        if marked == prefer_marked then
          return it
        end
        fallback = fallback or it
      end
    end
  end
  return fallback
end

-- HPの残り割合から損壊度を推定する（死体が見つからなかったとき用）
local function guess_dl_from_hp(mon)
  local hp_max = mon:get_hp_max()
  if not hp_max or hp_max <= 0 then
    return 0
  end
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

-- 効果の付与。強度付きが通らない環境でも落ちないようにしておく
local function add_effect_safe(mon, eff, dur, intensity)
  if intensity then
    local ok = pcall(function()
      mon:add_effect(eff, dur, nil, intensity)
    end)
    if ok then
      return
    end
  end
  pcall(function()
    mon:add_effect(eff, dur)
  end)
end

----------------------------------------------------------------------
-- 復活したモンスターを弱らせる
----------------------------------------------------------------------

local function handle_revived(mon)
  -- revive_corpse() は蘇らせた直後に downed を 5 ターン付ける。
  -- 通常のスポーンには付かないので、これを「復活してきた個体」の判定に使う。
  if not mon:has_effect(EFF_DOWNED) then
    return
  end
  if not mon:has_flag(MonsterFlag.REVIVES) then
    return
  end
  if not mon:in_species(SPECIES_ZOMBIE) then
    return
  end
  -- プレイヤーが作ったゾンビ奴隷(zlave)は対象外
  if mon:has_effect(EFF_PET) or mon:has_effect(EFF_PACIFIED) then
    return
  end

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

  -- 1) HPの上限を損壊度で押さえる
  local ratio = mod.cfg.hp_ratio[dl] or 0.5
  local hp_max = mon:get_hp_max()
  local target = math.floor(hp_max * ratio)
  if target < 1 then
    target = 1
  end
  local cur = mon:get_hp()
  if target < cur then
    mon:set_hp(target)
  end

  -- 2) 起き上がるまでしばらく無力にする
  local secs = mod.cfg.rise_secs[dl]
  if secs and secs > 0 then
    local dur = TimeDuration.from_seconds(secs)
    add_effect_safe(mon, EFF_DOWNED, dur)
    add_effect_safe(mon, EFF_STUNNED, dur)
  end

  -- 3) 死後硬直（移動速度低下）
  local mins = mod.cfg.rigor_mins[dl]
  if mins and mins > 0 then
    add_effect_safe(mon, EFF_RIGOR, TimeDuration.from_minutes(mins), dl + 1)
  end

  -- 4) 何度目の復活かを個体に記録しておく（死亡時に死体へ書き戻す）
  mon:set_value(VAR_GEN, tostring(gen + 1))

  log("revived %s: dl=%d gen=%d hp=%d/%d", mon:get_name(), dl, gen + 1, mon:get_hp(), hp_max)
end

mod.on_monster_spawn = function(params)
  local mon = params and params.monster
  if not mon then
    return
  end
  local ok, err = pcall(handle_revived, mon)
  if not ok then
    gdebug.log_info("LRZ: on_monster_spawn failed: " .. tostring(err))
  end
end

----------------------------------------------------------------------
-- 蘇った個体が倒れたら、その死体に回数を刻む
----------------------------------------------------------------------

local function handle_death(mon)
  if not mon:has_flag(MonsterFlag.REVIVES) then
    return
  end
  if not mon:in_species(SPECIES_ZOMBIE) then
    return
  end

  local gen = tonumber(mon:get_value(VAR_GEN)) or 0
  if gen < 1 and mod.cfg.max_revivals > 0 then
    -- 一度も蘇っていない個体。最初の死体は普通に起き上がれる。
    return
  end

  local pos = mon:get_pos_ms()
  local corpse = find_corpse_at(pos, mon:get_type():str(), false)
  if not corpse then
    return
  end

  corpse:set_var_num(VAR_GEN, gen)

  if gen >= mod.cfg.max_revivals then
    -- PULPED は本体が「潰した死体」に付ける印。can_revive() がこれを見て弾く。
    corpse:set_flag(FLAG_PULPED)
    log("corpse of %s sealed (gen=%d)", mon:get_name(), gen)
    if mod.cfg.announce then
      local u = gapi.get_avatar()
      if u and u:sees(pos) then
        gapi.add_msg(MsgType.good,
          string.format(locale.gettext("The %s is too broken to rise again."), mon:get_name()))
      end
    end
  end
end

mod.on_mon_death = function(params)
  if not params then
    return
  end
  local mon = params.mon or params.creature
  if not mon then
    return
  end
  -- Creature として渡ってきた場合に備える
  local as_mon = nil
  pcall(function()
    as_mon = mon:as_monster()
  end)
  if as_mon then
    mon = as_mon
  end
  local ok, err = pcall(handle_death, mon)
  if not ok then
    gdebug.log_info("LRZ: on_mon_death failed: " .. tostring(err))
  end
end

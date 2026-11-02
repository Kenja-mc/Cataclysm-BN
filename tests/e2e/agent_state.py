from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from agent_actions import (  # noqa: F401  (ActionSpec is re-exported for callers)
    ActionSpec,
    actions_for,
    classify_screen,
    framed_title,
    menu_rows,
    x11_keys,
)

MAX_TEXT = 6000
MAX_SCREEN_LINES = 45
TUTORIAL_NAME = "John Smith"


@dataclass(frozen=True)
class StateDump:
    text: str
    actions: tuple[ActionSpec, ...]
    menu: str | None
    image: bytes | None


_STATE_LUA = (
    "function AGS_P(dx,dy) local c=gapi.get_avatar():get_pos_ms() "
    "return TripointBubMs.new(c.x+dx,c.y+dy,c.z) end "
    "function AGS_T(s,n) s=(s or ''):gsub('<[^>]*>',''):gsub('%s+',' ') "
    "if #s>n then s=s:sub(1,n-1)..'~' end return s end "
    "function AGS_L(t,w) local s=table.concat(t,'; ') if #s>w then s=s:sub(1,w-1)..'~' end "
    "return s end "
    "function AGS_I(it) local s=AGS_T(it:display_name(1),34):gsub('^[^%w]+','') "
    "if it:is_stackable() then s=s..'x'..it.charges end return s end "
    "function AGS_DUMP() local a=gapi.get_avatar() local M=gapi.get_map() local p=a:abs_pos() "
    "local pb=a:get_pos_ms() "
    "out('name='..AGS_T(a:get_name(),20)..' hp='..a:get_hp()..'/'..a:get_hp_max()) "
    "out('pos='..p.x..','..p.y..','..p.z) "
    "out('needs=thirst'..a:get_thirst()..' kcal'..a:get_stored_kcal()..' sleep'..a:get_sleep_deprivation()) "
    "out('sta='..a:get_stamina()..'/'..a:get_stamina_max()..' pain='..a:get_pain()"
    "..' morale='..a:get_morale_level()..' focus='..a.focus_pool) "
    "local w={} for _,it in ipairs(a:get_worn_items()) do w[#w+1]=AGS_I(it) end "
    "out('worn('..#w..')='..AGS_L(w,50)) "
    "local h={} local inv={} for _,it in ipairs(a:all_items(false)) do "
    "if a:is_wielding(it) then h[#h+1]=AGS_I(it) elseif not a:is_worn(it) then inv[#inv+1]=AGS_I(it) end end "
    "out('wielding('..#h..')='..AGS_L(h,40)) out('carried('..#inv..')='..AGS_L(inv,50)) "
    "out('terrain='..AGS_T(M:get_ter_at(AGS_P(0,0)):str_id():str(),50)) "
    "local f={} for _,it in pairs(M:get_items_at(AGS_P(0,0))) do f[#f+1]=AGS_I(it) end "
    "out('underfoot('..#f..')='..AGS_L(f,50)) "
    "local c={} for _,cr in ipairs(a:get_visible_creatures(20)) do local q=cr:get_pos_ms() "
    "c[#c+1]=AGS_T(cr:get_name(),16)..'@'..(q.x-pb.x)..','..(q.y-pb.y)..' hp'..cr:get_hp() end "
    "out('visible('..#c..')='..AGS_L(c,50)) "
    "local n={} for dx=-3,3 do for dy=-3,3 do if dx~=0 or dy~=0 then local q=AGS_P(dx,dy) "
    "if a:sees(q) then local o={} for _,it in pairs(M:get_items_at(q)) do o[#o+1]=AGS_I(it) end "
    "if o[1] then n[#n+1]=dx..','..dy..' '..table.concat(o,'+') end end end end end "
    "out('nearby('..#n..')='..AGS_L(n,50)) out('done') end "
)


def _ensure_lua(game) -> bool:
    if getattr(game, "_agent_state_lua", False):
        return True
    game.define_lua(_STATE_LUA)
    game._agent_state_lua = True
    return True


def read_lua_state(game) -> list[str]:
    if not hasattr(game, "lua"):
        return []
    try:
        _ensure_lua(game)
        lines = _dump_lines(game)
        if "done" not in lines:
            game.lua("gdebug.clear_lua_log() out('ok')")
            lines = _dump_lines(game)
    except Exception as error:
        return [f"lua_error={type(error).__name__}: {error}"]
    out = []
    for line in lines:
        if line == "done":
            break
        out.append(line)
    if "done" not in lines:
        out.insert(0, f"[state truncated: only the newest {len(out)} fields are shown]")
    return out


def _dump_lines(game) -> list[str]:
    return game.lua("AGS_DUMP()")


def read_state_fields(handle) -> list[str]:
    path = None
    for source in (handle, getattr(handle, "game", None), getattr(handle, "tiles", None)):
        value = getattr(source, "state_path", None)
        if value:
            path = Path(value)
            break
    if path is None:
        return []
    try:
        state = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        return [f"state_error={type(error).__name__}: {error}"]
    player = state.get("player") or {}
    pos = player.get("pos") or [0, 0, 0]
    wielded = player.get("wielded") or ""
    worn = player.get("worn") or []
    fields = [
        f"turn={state.get('turn', -1)} input_wait={str(bool(state.get('input_wait'))).lower()}",
        f"name={player.get('name', '')} hp={player.get('hp', 0)}",
        "pos=" + ",".join(str(value) for value in pos),
        f"sta={player.get('stamina', 0)} pain={player.get('pain', 0)} "
        f"morale={player.get('morale', 0)}",
        f"wielding({1 if wielded else 0})={wielded}",
        f"worn({len(worn)})=" + "; ".join(worn),
    ]
    top = (state.get("ui") or {}).get("top")
    if top:
        fields.append(f"ui={top.get('id', '')} selected={top.get('selected', -1)}")
    return fields


def _trim_screen(screen: str) -> tuple[str, int]:
    lines = [line.rstrip() for line in screen.rstrip("\n").splitlines()]
    if len(lines) <= MAX_SCREEN_LINES:
        return "\n".join(lines), 0
    return "\n".join(lines[-MAX_SCREEN_LINES:]), len(lines) - MAX_SCREEN_LINES


def build_text(mode: str, menu: str | None, fields: list[str], screen: str, note: str = "",
               budget: int = MAX_TEXT) -> str:
    head = [f"mode={mode}", f"menu={menu or 'unknown'}"]
    if note:
        head.append(note)
    body = list(fields)
    if screen:
        kept, dropped = _trim_screen(screen)
        marker = f"[... {dropped} older screen lines trimmed ...]" if dropped else ""
        body += ["-- screen --"] + ([marker] if marker else []) + kept.splitlines()
    room = budget - sum(len(line) + 1 for line in head)
    while body and sum(len(line) + 1 for line in body) > room:
        body.pop(0)
    return "\n".join(head + body)


def _game_of(handle):
    game = getattr(handle, "game", None)
    if game is not None:
        return game
    if hasattr(handle, "screen") or hasattr(handle, "lua"):
        return handle
    raise RuntimeError("no curses game on this handle: expected .game (or a tmux_game.Game)")


def _tiles_of(handle):
    tiles = getattr(handle, "tiles", None)
    if tiles is None:
        raise RuntimeError("no tiles session on this handle: expected .tiles")
    return tiles


def _tiles_display(handle):
    tiles = _tiles_of(handle)
    for source in (tiles, getattr(tiles, "session", None), handle):
        display = getattr(source, "display", None)
        if display:
            return display
    raise RuntimeError("tiles capture needs a display: set .display on the handle or .tiles")


def _tiles_window(handle):
    tiles = _tiles_of(handle)
    for name in ("window_id", "window", "win"):
        window = getattr(tiles, name, None)
        if isinstance(window, int):
            return window
    x11 = _tiles_x11(handle)
    window = x11.find_window("Cataclysm")
    if window is None:
        raise RuntimeError("tiles window not found: expose .window_id/.win on .tiles")
    return window


def _tiles_x11(handle):
    tiles = _tiles_of(handle)
    x11 = getattr(tiles, "x11", None) or getattr(getattr(tiles, "session", None), "x11", None)
    if x11 is not None:
        return x11
    own = getattr(tiles, "_agent_state_x11", None)
    if own is None:
        import tiles as tiles_module
        own = tiles_module.X11(_tiles_display(handle))
        tiles._agent_state_x11 = own
    return own


def close_tiles(handle) -> None:
    tiles = getattr(handle, "tiles", None)
    own = getattr(tiles, "_agent_state_x11", None)
    if own is not None:
        own.close()
        tiles._agent_state_x11 = None


def capture_tiles(handle) -> bytes:
    tiles = _tiles_of(handle)
    capture = getattr(tiles, "capture", None)
    if callable(capture):
        return Path(capture()).read_bytes()
    import tiles as tiles_module
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        png = Path(tmp.name)
    tiles_module.capture(_tiles_display(handle), _tiles_window(handle), png)
    try:
        return png.read_bytes()
    finally:
        png.unlink(missing_ok=True)


def _button(action: ActionSpec) -> int:
    return 2 if action.id.startswith("secondary_") else 0


def send_action(handle, action: ActionSpec, *, mode: str) -> None:
    if mode == "tiles":
        tiles = _tiles_of(handle)
        if action.click is not None:
            x, y = action.click
            x11 = _tiles_x11(handle)
            x11.focus_local(_tiles_window(handle), x, y)
            for _ in range(action.clicks):
                x11.click(_button(action) + 1)
        if action.keys:
            keys = x11_keys(action.keys)
            sender = getattr(tiles, "key", None)
            if callable(sender):
                sender(*keys)
            else:
                _tiles_x11(handle).key(*keys)
        return
    game = _game_of(handle)
    if action.keys:
        game.keys(*action.keys)
    if action.click is not None:
        for i in range(action.clicks):
            game.click(*action.click, button=_button(action), settle=i == action.clicks - 1)


def dump_state(handle, *, mode: str, capture_image: bool = False, scheme: str = "modern",
               mouse: bool = False, budget: int = MAX_TEXT) -> StateDump:
    if mode == "tiles":
        fields = read_state_fields(handle)
        if not fields and not capture_image:
            raise RuntimeError("the tiles build has no text state: start it with --state-out, or "
                               "call dump_state(..., mode='tiles', capture_image=True) and read "
                               "the image")
        image = capture_tiles(handle) if capture_image else None
        note = ("tiles build: text fields come from the game's state file; decide from the image"
                if fields else "tiles build: no text channel, decide from the image")
        text = build_text(mode, None, fields, "", note=note, budget=budget)
        return StateDump(text, actions_for("game", mode=mode, scheme=scheme, mouse=False),
                         None, image)
    game = _game_of(handle)
    screen = game.screen()
    colored = game.screen_colors() if hasattr(game, "screen_colors") else ""
    menu = classify_screen(screen)
    note = ""
    if menu in ("game", "tutorial"):
        fields = read_lua_state(game)
        if fields and not fields[0].startswith("lua_error"):
            game._agent_state_fields = fields
    else:
        fields = list(getattr(game, "_agent_state_fields", []))
        if fields:
            note = "exact fields are from the last gameplay turn: reading them would close this menu"
    if menu == "game" and any(line == f"name={TUTORIAL_NAME}" for line in fields):
        menu = "tutorial"
    text = build_text(mode, menu, fields, screen, note=note, budget=budget)
    actions = actions_for(menu, mode=mode, scheme=scheme, mouse=mouse, text=screen, colored=colored)
    return StateDump(text, actions, menu, None)

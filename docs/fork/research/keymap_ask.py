#!/usr/bin/env python3
"""Ask the decision models to pick default keybindings, with the survey in the state.

    XPL_SK_AGENT=... python3 keymap_ask.py [model] [out.json]

CONTROLS_RESEARCH points at the controls-research checkout (default ../controls-research).

State = cross-game patterns + genre conventions + the current CBN modern bindings for the
actions under decision + the fork's constraints. Each question offers 2-5 candidate bindings
with a rubric per candidate.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

REPO = os.environ.get("BN_REPO", str(Path(__file__).resolve().parents[3]))
RESEARCH = os.environ.get("CONTROLS_RESEARCH", "../controls-research")
URL = "https://api.experientiallabs.ai/v1/systemone"


def jev_key():
    """The Experiential Labs key, from the same variable the playtest harness reads."""
    key = os.environ.get("XPL_SK_AGENT")
    if not key:
        sys.exit("set XPL_SK_AGENT to an Experiential Labs key")
    return key


def sections(path, marks):
    text = open(path).read()
    out = []
    for start_mark, end_mark in marks:
        a = text.find(start_mark)
        b = text.find(end_mark) if end_mark else len(text)
        out.append(text[a:b] if a != -1 else "")
    return "\n".join(out)


def current_bindings(ids):
    base = json.load(open(f"{REPO}/data/raw/keybindings/keybindings.json"))
    modern = json.load(open(f"{REPO}/data/raw/control_schemes/modern.json"))
    merged = {(e.get("category") or "UNCAT", e["id"]): e for e in base}
    merged.update({(e.get("category") or "UNCAT", e["id"]): e for e in modern})
    rows = []
    for (cat, ident), e in sorted(merged.items()):
        if cat != "DEFAULTMODE" or ident not in ids:
            continue
        keys = []
        for b in e.get("bindings", []):
            k = b["key"]
            keys.append("+".join(k) if isinstance(k, list) else k)
        rows.append(f"- {ident} ({e.get('name', '')}): " +
                    (", ".join(f"`{k}`" for k in keys) if keys else "UNBOUND"))
    return "\n".join(rows)


def state(ids):
    patterns = sections(f"{RESEARCH}/control-schemes-survey.md", [
        ("## 4. Common control scheme patterns", "## 5. Recommendations"),
        ("## 5. Recommendations", "\n---\n"),
    ])
    games = sections(f"{RESEARCH}/control-schemes-survey.md", [
        ("## 2. Survival / base-building games", "## 4. Common control scheme patterns"),
    ])
    return f"""You advise on the DEFAULT keyboard scheme of the Bright Nights Overhaul fork of
Cataclysm: Bright Nights (CBN): a turn-based grid survival roguelike. 8-direction grid movement,
mouse aiming for ranged combat, modal menus, vehicles, and a large verb set. The fork makes the
game easier to learn without changing balance; a classic vi-key scheme ships untouched and every
key stays rebindable.

Two evidence sources follow: the cross-game control survey (genre conventions with sources) and
the current CBN modern bindings for the actions being decided.

{patterns}

---

GENRE CONTROL DETAILS (from the same survey):

{games}

---

CURRENT CBN MODERN BINDINGS FOR THE ACTIONS UNDER DECISION:

{current_bindings(ids)}

---

Constraints every candidate obeys: classic scheme untouched; a key must be free in the context it
is bound in; `w a s d q e z c` move the player, so no gameplay verb may use those letters without a
modifier; `Shift`+letter currently means the capital letter, which the modern scheme uses for
look-around. Prefer a single key of the genre-standard meaning; use a chord only where a collision
is unavoidable. Answer with the binding the default should ship.
"""


# question id -> (instructions, {option: rubric})
Q = {
    "look_layer": (
        "How should looking around (nudging the map view) be bound in gameplay? The current modern "
        "scheme uses capital W/A/S/D/Q/E/Z/C, which means Shift+movement letters; a wrong case "
        "currently does the other thing.",
        {"alt_wasd": "Alt+WASD and Alt+QEZC, a modifier the game leaves unused; frees every capital letter for verbs",
         "capital_wasd": "capital W/A/S/D (Shift+letter), current CBN modern scheme; keeps the case split",
         "shift_wasd": "Shift+WASD as a real chord, read as a modifier rather than a case",
         "unbound_look": "leave look unbound in gameplay; the minimap, map screen and mouse handle it"}),
    "pickup": (
        "Which keys pick items up? Classic CBN uses g for one tile and G (or ,) for everything "
        "nearby; the current modern scheme binds only g = pick up all.",
        {"g_all": "g picks up everything nearby (modern today); one key for the common case",
         "g_one_G_all": "g picks up one tile, G picks up everything nearby, as classic CBN",
         "g_one_ctrl_g_all": "g picks up one tile, Ctrl+G picks up everything nearby"}),
    "drop": (
        "Which binding drops the selected item? d is move-east; classic CBN used d to drop.",
        {"ctrl_d": "Ctrl+D, a chord that keeps the classic letter",
         "panel_only": "keep drop in the inventory item panel and the action menu only",
         "alt_d": "Alt+D"}),
    "wield": (
        "Which binding wields the selected item? Classic shares w with movement, the modern scheme "
        "keeps wield inside the inventory item panel.",
        {"panel_h": "h in the inventory item panel only (modern today)",
         "ctrl_w": "Ctrl+W in gameplay plus the panel",
         "action_menu_only": "action menu only"}),
    "wear": (
        "Which binding wears the selected item?",
        {"panel_W": "W in the inventory item panel only (modern today)",
         "ctrl_wear": "Ctrl+W in gameplay plus the panel",
         "action_menu_only": "action menu only"}),
    "eat": (
        "Which binding eats food or drinks? Classic CBN used e, which now moves north-east.",
        {"N_nutrition": "N, next to the auto-explore key, readable as nutrition",
         "ctrl_e": "Ctrl+E, keeping the classic letter behind a chord",
         "action_menu_only": "action menu only"}),
    "apply_use": (
        "Which binding applies or uses a held item (tools, books, activators)?",
        {"U_use": "U, mnemonic for use",
         "a_apply": "Ctrl+A, keeping the classic apply letter",
         "action_menu_only": "action menu only"}),
    "read": (
        "Which binding reads a book or item?",
        {"R_read": "R, classic CBN",
         "ctrl_r": "Ctrl+R, because r reloads",
         "action_menu_only": "action menu only"}),
    "take_off": (
        "Which binding takes off a worn item?",
        {"T_takeoff": "T, classic CBN and the case pair of t = throw",
         "ctrl_t": "Ctrl+T",
         "action_menu_only": "action menu only"}),
    "unload": (
        "Which binding unloads a wielded item?",
        {"ctrl_u": "Ctrl+U, keeping the classic U behind a chord",
         "panel_only": "inventory item panel only",
         "action_menu_only": "action menu only"}),
    "craft": (
        "Which binding opens crafting?",
        {"ampersand": "&, classic CBN",
         "c_craft": "C, mnemonic craft",
         "action_menu_only": "action menu only"}),
    "advinv": (
        "Which binding opens the advanced (multi-column) inventory?",
        {"I_upper": "I, the case pair of i = inventory",
         "slash": "/, classic CBN; but lists already use / as filter",
         "action_menu_only": "action menu only"}),
    "save_quit": (
        "How should save-and-quit be reachable? s moves south and Esc opens the menu that already "
        "lists it.",
        {"menu_only": "the main menu only (Esc then the entry), as proposed",
         "ctrl_s": "Ctrl+S everywhere",
         "unbound": "a dedicated key left unbound by default for players to set"}),
    "wait": (
        "Which binding waits one turn?",
        {"dot": ". the roguelike standby/wait convention (classic CBN used . for pause)",
         "ctrl_x": "Ctrl+X, the modern binding paired with x = pause",
         "both": "both . and Ctrl+X"}),
    "jump": (
        "Which binding jumps over an adjacent tile? Space examines terrain today and classic CBN "
        "used Space to jump.",
        {"ctrl_space": "Ctrl+Space",
         "j_unused": "j, the NetHack jump letter",
         "action_menu_only": "action menu only"}),
    "center_view": (
        "Which binding centers the view on the player?",
        {"home": "Home, the genre key",
         "colon": ": the classic CBN key",
         "both_home_colon": "Home with : as a classic alias"}),
    "vehicle": (
        "Which binding enters or opens vehicle controls?",
        {"V_upper": "V, mnemonic and easy to reach, with ^ as a classic alias",
         "caret_only": "^, classic CBN, physically awkward",
         "ctrl_v": "Ctrl+V"}),
    "doors": (
        "How should opening and closing doors be bound? Classic used o = open and c = close; c now "
        "moves south-east.",
        {"o_toggle": "o toggles the door, open or closed",
         "o_toggle_ctrl_c": "o toggles, Ctrl+C closes",
         "action_menu_only": "the tile action menu only"}),
    "smash": (
        "Which binding smashes nearby terrain? s moves south.",
        {"ctrl_v": "Ctrl+V for violence",
         "action_menu_only": "the tile action menu only",
         "unbound": "leave unbound"}),
    "autoattack": (
        "Should the classic autoattack toggle be restored in gameplay?",
        {"tab_gameplay": "Tab toggles autoattack in gameplay, and cycles targets in the targeting screen",
         "leave_unbound": "leave it unbound; executive actions come from the action menu"}),
    "pause": (
        "Which binding pauses (waits a turn when nothing threatens)? Modern ships x, while Esc opens "
        "the menu and every action game uses Esc for pause.",
        {"x_today": "x, the current modern binding, with numpad 5",
         "esc_pause": "Esc pauses, and the menu moves behind a different key",
         "space_pause": "Space pauses"}),
    "examine": (
        "Which binding examines the tile in front of or under the player?",
        {"space": "Space, the genre interact key and the modern binding",
         "e_interact": "Ctrl+E, because e moves north-east",
         "enter": "Enter, the action menu"}),
    "attack_dir": (
        "Attack in a direction is unbound in the modern scheme: walking into an enemy attacks, and "
        "there is no ranged swing. Should it get a default?",
        {"unbound": "leave unbound; movement attacks and f fires",
         "ctrl_dir": "Ctrl+direction for a deliberate attack without moving",
         "alt_dir": "Alt+direction"}),
    "overmap_pan": (
        "How should the overmap pan the view?",
        {"wasd": "WASD/arrows/numpad, one spatial language everywhere",
         "hjkl": "H/J/K/L, the current overmap-only pan keys",
         "wasd_plus_hjkl": "WASD plus H/J/K/L aliases"}),
    "quicksave": (
        "Which quicksave and quickload keys should ship?",
        {"f5_f9": "F5 save, F9 load, the genre pair",
         "unbound": "unbound by default",
         "ctrl_s_ctrl_l": "Ctrl+S and Ctrl+L"}),
    "quick_stack": (
        "Which binding quick-stacks the inventory into nearby storage? The fork ships this action; "
        "it is unbound in modern.",
        {"ctrl_g": "Ctrl+G, next to g = pick up",
         "panel_only": "inventory panel only",
         "unbound": "leave unbound"}),
    "missions": (
        "Which binding opens missions, messages, player info and other status screens? Choose the "
        "family's shape.",
        {"classic_caps": "classic capitals: M missions, P messages, @ info, # factions, p bionics, [ mutations",
         "single_menu": "one journal hub under J with the rest inside",
         "mirror_modern": "keep the modern set and add only what is missing"}),
    "view_zoom": (
        "Which zoom bindings should ship for the map?",
        {"wheel_plus_minus": "mouse wheel plus = and - (and numpad +/-)",
         "wheel_only": "the mouse wheel only",
         "keys_only": "= and - only"}),
    "movement_menu": (
        "Should the movement-mode menu (run/walk/crouch/prone) get a default key?",
        {"quote": "\" the classic CBN key, beside X = cycle",
         "unbound": "leave unbound; X cycles every mode",
         "ctrl_m_modes": "Ctrl+M"}),
    "fire_mode": (
        "Which binding toggles the firing mode (single/burst/auto) of the wielded weapon?",
        {"F_upper": "F, the classic case pair of f = fire",
         "ctrl_f": "Ctrl+F",
         "unbound": "leave unbound"}),
    "classic_layer": (
        "How much of the classic capital-verb layer (B butcher, R read, T take off, $ sleep, & craft, "
        "* construct, ( disassemble, - recraft, = organize, + sort armor, \\ haul, ] spell) should "
        "the modern scheme restore as gameplay defaults?",
        {"restore_all_free": "restore every classic verb whose letter is still free next to WASD",
         "restore_common": "restore only the common ones (butcher, read, take off, sleep, craft, construct)",
         "menu_first": "leave them to the action menu and ship almost no mnemonic overload"}),
    "gamepad": (
        "How much gamepad support should the default scheme claim? Today only menus bind JOY_*.",
        {"menus_only": "menus and lists only, as today",
         "full_profile": "a full gameplay profile: left stick move, right stick look/aim, RT fire, A interact",
         "separate_preset": "a separate gamepad control scheme, not part of the keyboard default"}),
}


def ask(model, qids):
    body = {"model": model, "state": STATE,
            "questions": {q: {"type": "choice", "instructions": Q[q][0][:600],
                              "criteria": Q[q][1]} for q in qids}}
    raw = json.dumps(body).encode()
    req = urllib.request.Request(URL, data=raw, headers={
        "Authorization": f"Bearer {jev_key()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.load(r)


if __name__ == "__main__":
    ids = {"look", "peek", "ctrl_w", "shift_w", "pickup", "pickup_feet", "grab", "drop", "drop_adj",
           "wield", "wear", "eat", "apply", "apply_wielded", "read", "take_off", "unload",
           "craft", "advinv", "save", "wait", "jump", "center", "control_vehicle", "open", "close",
           "smash", "autoattack", "pause", "examine", "attack", "missions", "messages", "player_data",
           "factions", "bionics", "mutations", "quicksave", "quickload", "quick_stack",
           "select_fire_mode", "open_movement", "toggle_manual_combat_mode", "haul", "butcher",
           "sleep", "construct", "disassemble", "recraft", "organize", "sort_armor", "cast_spell"}
    STATE = state(ids)
    print(f"state chars: {len(STATE)}", file=sys.stderr)
    model = sys.argv[1] if len(sys.argv) > 1 else "jev-latest"
    out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/jev2.json"
    qids = list(Q)[:32]
    result = ask(model, qids)
    json.dump(result, open(out, "w"), indent=1)
    for q, a in result.get("answers", {}).items():
        top = max(a.get("probabilities", {}).items(), key=lambda kv: kv[1], default=("?", 0))
        print(f"{q:18} {a.get('choice'):20} conf={a.get('confidence')} p={top[1]:.2f}")

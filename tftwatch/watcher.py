"""Background lobby watcher — fully automatic, no manual screenshots.

Continuously samples the right-side player-list region in memory (via mss). Frames
are NEVER written to disk during play; only when the panel meaningfully changes and
settles does it read the lobby, then hand the read to Coach Roland for advice.

Coach Roland only ever observes and suggests — it reads your own screen + public
data and advises. It never automates input, never reads memory, never overlays the
game. You make every call.

Two coaching engines:
  - the reasoning BRAIN (default when an OpenAI key is set) — synthesizes one plan
    from your comp, your partner's, the lobby, the augment ledger, and the meta;
  - the deterministic RULES coach (fallback, or with --rules-only) — fast template
    nudges, no extra LLM cost.

If you tell it which comp you're playing (and your Double Up partner's), the advice
becomes contest-aware. The augment ledger fills in opportunistically as boards come
on screen (yours continuously with --augments; others when you scout them).

    python -m tftwatch.watcher --comp dark_star_jhin --partner Wisp --partner-comp samira_reroll
    python -m tftwatch.watcher --comp dark_star_jhin --rules-only   # no LLM brain
    python -m tftwatch.watcher --once                           # save one panel crop for tuning, NO API call
"""
import os
import time
import atexit
import argparse

import mss
import numpy as np
from PIL import Image

from . import compguide
from . import brain
from .ledger import Ledger
from .vision import (read_lobby_pil, read_board_pil, read_augments_pil, read_self_pil,
                     _crop_region, RIGHT_PANEL)
from .coach import CoachRoland
from .cleanup import capture_dir, purge_captures

SELF = "me"   # ledger key for your own augments


def _grab_full(sct, monitor) -> Image.Image:
    shot = sct.grab(monitor)
    return Image.frombytes("RGB", shot.size, shot.rgb)


def _signature(full_img: Image.Image) -> np.ndarray:
    """Tiny grayscale fingerprint of the panel region for cheap change detection."""
    panel = _crop_region(full_img, RIGHT_PANEL)
    small = panel.convert("L").resize((24, 64))
    return np.asarray(small, dtype=np.int16)


def _changed(a, b, threshold: float = 6.0) -> bool:
    if a is None or b is None:
        return True
    return float(np.abs(a - b).mean()) > threshold


def _comp_context(comp_key, partner_name, partner_comp_key):
    """Turn declared comp keys (or carry names) into the dicts the coach wants."""
    my_comp = my_plan = teammate_comp = None

    c = compguide.find(comp_key) if comp_key else None
    if c:
        carry = c.get("carry")
        has_carry = bool(carry) and carry.lower() != "flex"
        my_comp = {
            "name": c.get("name"), "carry": carry,
            "carries": [carry] if has_carry else [],
            "carry_items": c.get("carry_items", []),
            "carry_components": c.get("carry_components", []),
            "flexible_components": c.get("flexible_components", []),
            "source": c.get("source"),
        }
        my_plan = {
            "name": c.get("name"), "carry": carry,
            "early_units": c.get("early_units"),
            "level_plan": c.get("level_plan"), "source": c.get("source"),
        }

    if partner_comp_key or partner_name:
        pc = compguide.find(partner_comp_key) if partner_comp_key else None
        pcarry = pc.get("carry") if pc else None
        has_pcarry = bool(pcarry) and pcarry.lower() != "flex"
        teammate_comp = {"name": partner_name, "carries": [pcarry] if has_pcarry else []}
    return my_comp, my_plan, teammate_comp


def _smooth_hp(players, hp_hist, max_drop: int = 25) -> None:
    """Reject implausible single-read HP crashes — the vision misreads tiny HP digits
    (e.g. '89' -> '9'). A player can't lose more than ~one combat (~25) in a round, so a
    bigger drop is treated as a misread and the last good value is kept. Mutates players.
    """
    for p in players:
        name, hp = p.get("name"), p.get("hp")
        if not name or not isinstance(hp, int):
            continue
        prev = hp_hist.get(name)
        if prev is not None and hp < prev - max_drop:
            p["hp"] = prev                 # implausible crash -> keep last known HP
        else:
            hp_hist[name] = hp


def _contested_carries(data: dict) -> list[str]:
    """Carries 2+ players are currently shown spiking on — the live 'what's hot' read.

    The lobby panel only reveals a unit when someone recently starred it up, so this
    is a partial signal (sharpest during multi-spike moments); we surface what we can.
    """
    units = [p.get("unit") for p in (data.get("players") or []) if p.get("unit")]
    return sorted({u for u in units if units.count(u) >= 2})


def _assemble_state(comp_key, my_comp, teammate_comp, partner_name, data, contested,
                    ledger: Ledger, stage: str = "unknown",
                    self_read: dict = None, owned_units=None,
                    traits=None, committed_comp=None) -> dict:
    """Bundle everything the brain reasons over, pulling augments/carries from the ledger.

    self_read = {gold, level, shop:[{name,cost}]} from the bottom-bar reader; owned_units
    = names currently on your board/bench (from the board read) for replace advice.
    """
    players = data.get("players") or []
    opponents = []
    for p in players:
        if p.get("is_self"):
            continue
        name = p.get("name")
        if not name or name == partner_name:
            continue
        opponents.append({
            "name": name,
            "carry": ledger.carry_for(name) or p.get("unit"),
            "augments": ledger.augments_for(name) or ["unknown (not scouted)"],
        })

    me = {"comp": comp_key, "carry": (my_comp or {}).get("carry"),
          "augments": ledger.augments_for(SELF) or ["unknown"]}
    if self_read:
        me["gold"] = self_read.get("gold")
        me["level"] = self_read.get("level")
        me["shop"] = [s.get("name") for s in (self_read.get("shop") or [])
                      if s and s.get("name")]
    if traits:
        me["active_traits"] = traits          # [{name,count}] — what you're ACTUALLY building
    if owned_units:
        me["board_and_bench"] = owned_units

    partner = None
    if teammate_comp or partner_name:
        pcarries = (teammate_comp or {}).get("carries") or []
        partner = {"name": partner_name,
                   "carry": pcarries[0] if pcarries else None,
                   "augments": ledger.augments_for(partner_name) or ["unknown (not scouted)"]}

    return {
        "stage": stage,
        "mode": "doubleup" if partner else "standard",
        "me": me, "partner": partner, "opponents": opponents,
        "contested": contested, "next_opponent": data.get("next_opponent"),
        "committed_comp": committed_comp,    # keep this unless traits clearly say otherwise
    }


def _rules_advice(coach, my_comp, my_plan, teammate_comp, data, contested, augs, alt_name):
    """Deterministic fallback advice (no LLM). Mirrors the brain's coverage cheaply."""
    out = []
    if my_comp:
        carry = my_comp.get("carry")
        has_carry = bool(my_comp.get("carries"))
        is_contested = has_carry and carry.lower() in {c.lower() for c in contested}
        if has_carry:
            out += coach.early_game(my_plan)
            out += coach.item_plan(my_comp, contested=is_contested, alt=alt_name)
        if teammate_comp:
            out += coach.doubleup(my_comp, teammate_comp, data, augments=augs, alt_comp=alt_name)
        else:
            out += coach.contested_pivot(my_comp, data, augments=augs, alt_comp=alt_name)
        out += coach.recommend(contested, my_intended=carry)
    else:
        out += coach.recommend(contested)
    return out


def watch(poll: float = 1.0, settle: float = 1.0, min_gap: float = 6.0,
          model: str = "gpt-4o", on_update=None,
          comp_key: str = None, partner_name: str = None, partner_comp_key: str = None,
          board: bool = False, augments: bool = False, shop: bool = False,
          use_brain: bool = True, brain_gap: float = 18.0) -> None:
    """Watch the panel; read + coach when it changes and settles.

    use_brain — run the LLM reasoning brain (auto-off if no OPENAI_API_KEY); brain_gap
    throttles how often it's called (seconds) since each call costs tokens. Between
    calls the last plan is kept and fresh transient threats are layered on top.
    """
    purge_captures()
    atexit.register(purge_captures)
    coach = CoachRoland()
    ledger = Ledger()
    my_comp, my_plan, teammate_comp = _comp_context(comp_key, partner_name, partner_comp_key)
    brain_on = use_brain and bool(os.getenv("OPENAI_API_KEY"))

    bits = []
    if my_comp:
        bits.append(f"comp: {my_comp['name']}")
    if teammate_comp and teammate_comp.get("carries"):
        bits.append(f"partner anchors {teammate_comp['carries'][0]}")
    bits.append("brain" if brain_on else "rules")
    print(f"TFTwatch + Coach Roland running.  ({'; '.join(bits)})  Just play — it reads and "
          f"suggests on its own; you make every call. Ctrl+C to stop.\n")

    last_sig = None
    pending_since = None
    last_read = 0.0
    last_brain = 0.0
    last_brain_recs: list = []
    last_comp = compguide.comp_detail(comp_key) if comp_key else None
    hp_hist: dict = {}                     # per-player HP, to reject misread crashes
    empty_reads = 0

    with mss.MSS() as sct:
        monitor = sct.monitors[1]
        try:
            while True:
                full = _grab_full(sct, monitor)
                sig = _signature(full)
                now = time.time()

                if _changed(last_sig, sig):
                    last_sig = sig
                    pending_since = now
                elif pending_since and (now - pending_since) >= settle and (now - last_read) >= min_gap:
                    pending_since = None
                    last_read = now
                    try:
                        data = read_lobby_pil(full, model=model)
                    except Exception as e:
                        print(f"  (read failed: {e})")
                        time.sleep(poll)
                        continue

                    players = data.get("players") or []
                    if len(players) < 2:
                        empty_reads += 1
                        if empty_reads >= 2:
                            coach.reset()
                            ledger.reset()
                            last_brain_recs = []
                            last_comp = compguide.comp_detail(comp_key) if comp_key else None
                            hp_hist.clear()
                            removed = purge_captures()
                            if on_update:
                                on_update({"ts": time.strftime('%H:%M:%S'), "event": "game_over",
                                           "data": None, "advice": [], "positioning": [], "comp": None})
                            else:
                                print(f"[{time.strftime('%H:%M:%S')}] Game over — cleared session "
                                      f"memory; removed {removed} temp file(s).\n")
                            empty_reads = 0
                        time.sleep(poll)
                        continue

                    empty_reads = 0
                    _smooth_hp(players, hp_hist)               # correct misread HP before anyone uses it
                    coach.observe(data)                        # keep session tracking; output dropped (HP reads too noisy)
                    for p in players:                          # ledger: remember spiked carries
                        if p.get("unit") and p.get("name"):
                            ledger.note_carry(p["name"], p["unit"])
                    contested = _contested_carries(data)
                    open_list = compguide.open_comps(contested)
                    alt_name = open_list[0]["name"] if open_list else "an open line"

                    augs = []
                    if augments:
                        try:
                            augs = read_augments_pil(full, model=model).get("augments", [])
                            ledger.note_augments(SELF, augs)
                        except Exception as e:
                            print(f"  (augment read failed: {e})")

                    self_read = None
                    if shop:
                        try:
                            self_read = read_self_pil(full, model=model)
                        except Exception as e:
                            print(f"  (shop read failed: {e})")

                    # Traits = ground truth for which comp you're building -> read whenever the
                    # brain is on, so the comp pick is grounded in YOUR board, not random.
                    traits_read = None
                    if brain_on:
                        try:
                            traits_read = read_traits_pil(full, model=model).get("traits")
                        except Exception as e:
                            print(f"  (trait read failed: {e})")

                    # Board read feeds BOTH positioning and "replace this" owned-unit advice.
                    positioning, owned_units = [], None
                    if board:
                        try:
                            board_read = read_board_pil(full, model=model)
                            positioning = coach.positioning(board_read)
                            owned_units = [u.get("name") for u in (board_read.get("units") or [])
                                           if u.get("name")]
                        except Exception as e:
                            print(f"  (board read failed: {e})")

                    if brain_on:
                        if (now - last_brain) >= brain_gap:
                            last_brain = now
                            try:
                                state = _assemble_state(
                                    comp_key, my_comp, teammate_comp, partner_name, data,
                                    contested, ledger, self_read=self_read, owned_units=owned_units,
                                    traits=traits_read,
                                    committed_comp=(last_comp or {}).get("key"))
                                out = brain.advise(state)
                                last_brain_recs = out["recs"]
                                detail = compguide.comp_detail(out.get("comp_key"))
                                if not detail and out.get("comp_name"):
                                    # comp not in the curated DB (e.g. Space Groove) -> use the
                                    # brain's trait-grounded comp so the panel still shows it.
                                    detail = {"key": None, "name": out["comp_name"], "carry": None,
                                              "carry_items": [], "early_units": [],
                                              "board": out.get("comp_board") or [],
                                              "level_plan": "", "playstyle": None}
                                if detail:                       # keep last good comp if unresolved
                                    last_comp = detail
                            except Exception as e:
                                print(f"  (brain call failed: {e})")
                        strategic = last_brain_recs
                    else:
                        strategic = _rules_advice(coach, my_comp, my_plan, teammate_comp,
                                                  data, contested, augs, alt_name)

                    recs = strategic        # brain (or rules) only — no noisy per-read HP alerts

                    stamp = time.strftime('%H:%M:%S')
                    if on_update:
                        on_update({"ts": stamp, "event": "read", "data": data,
                                   "advice": recs, "positioning": positioning, "comp": last_comp})
                    elif recs:
                        print(f"[{stamp}]\n{coach.say(recs)}\n")
                    else:
                        print(f"[{stamp}] lobby read — no new threats.\n")
                time.sleep(poll)
        except KeyboardInterrupt:
            removed = purge_captures()
            print(f"\nstopped. removed {removed} temp file(s).")


def _once() -> None:
    """Capture one frame + save the panel crop to the managed temp dir. No API call."""
    out = capture_dir() / "panel_capture.png"
    with mss.MSS() as sct:
        full = _grab_full(sct, sct.monitors[1])
    print(f"captured full screen: {full.size}")
    _crop_region(full, RIGHT_PANEL).save(out)
    print(f"saved panel crop -> {out}\n(open it to check the region framing; it's auto-purged on next run)")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tftwatch.watcher", description="Live lobby watcher + Coach Roland")
    p.add_argument("--once", action="store_true",
                   help="save one panel crop for region tuning, no API call")
    p.add_argument("--comp", metavar="KEY|CARRY",
                   help="your line (compguide key or carry name) -> contest-aware advice")
    p.add_argument("--partner", metavar="NAME", help="Double Up partner's name")
    p.add_argument("--partner-comp", metavar="KEY|CARRY", help="partner's line")
    p.add_argument("--board", action="store_true", help="also read your board for positioning (extra vision call)")
    p.add_argument("--augments", action="store_true", help="also read your active augments (extra vision call)")
    p.add_argument("--shop", action="store_true", help="also read your shop/gold/level -> 'buy this' advice (extra vision call)")
    p.add_argument("--rules-only", action="store_true", help="deterministic rules coach, no LLM brain")
    return p


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    args = _build_parser().parse_args()
    if args.once:
        _once()
    else:
        watch(comp_key=args.comp, partner_name=args.partner, partner_comp_key=args.partner_comp,
              board=args.board, augments=args.augments, shop=args.shop, use_brain=not args.rules_only)

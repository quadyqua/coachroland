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
from . import localvision
from .ledger import Ledger
from .scout_detect import ScoutDetector
from .coaching import _comp_dicts, _rules_advice
from .tracker import PurchaseTracker, HitTracker
from .vision import (read_lobby_pil, read_board_pil, read_augments_pil, read_self_pil,
                     read_traits_pil, read_offer_pil, _crop_region, RIGHT_PANEL)
from .coach import CoachRoland
from .cleanup import capture_dir, purge_captures

SELF = "me"   # ledger key for your own augments

# Shop and traits are printed TEXT (champion names, trait names, gold/level numbers) — a
# small model reads them fine at a fraction of the cost. Lobby (tiny HP digits / star pips),
# board (isometric), and augments (icons, not text) stay on the stronger model.
TEXT_MODEL = os.getenv("TFT_TEXT_MODEL", "gpt-4o-mini")


def _grab_full(sct, monitor) -> Image.Image:
    shot = sct.grab(monitor)
    return Image.frombytes("RGB", shot.size, shot.rgb)


def _signature(full_img: Image.Image) -> np.ndarray:
    """Tiny grayscale fingerprint for cheap change detection. Includes the scoreboard
    panel AND the bench band, so buying/selling a unit (bench change) also triggers a
    fresh read -> Coach stays aware of your bench, not just the lobby."""
    panel = _crop_region(full_img, RIGHT_PANEL).convert("L").resize((24, 64))
    bench = _crop_region(full_img, localvision.BENCH_REGION).convert("L").resize((64, 8))
    return np.concatenate([np.asarray(panel, dtype=np.int16).ravel(),
                           np.asarray(bench, dtype=np.int16).ravel()])


def _signature_shop(full_img: Image.Image) -> np.ndarray:
    """Tiny fingerprint of just the shop / bottom-HUD strip, so a reroll triggers a
    fast shop-only read without waiting on the heavier lobby/traits cycle."""
    s = _crop_region(full_img, localvision.SELF_REGION).convert("L").resize((64, 10))
    return np.asarray(s, dtype=np.int16).ravel()


def _changed(a, b, threshold: float = 6.0) -> bool:
    if a is None or b is None:
        return True
    return float(np.abs(a - b).mean()) > threshold


def _comp_context(comp_key, partner_name, partner_comp_key):
    """Turn declared comp keys (or carry names) into the dicts the coach wants."""
    my_comp, my_plan = _comp_dicts(compguide.find(comp_key) if comp_key else None)
    teammate_comp = None
    if partner_comp_key or partner_name:
        pc = compguide.find(partner_comp_key) if partner_comp_key else None
        pcarry = pc.get("carry") if pc else None
        has_pcarry = bool(pcarry) and pcarry.lower() != "flex"
        teammate_comp = {"name": partner_name, "carries": [pcarry] if has_pcarry else []}
    return my_comp, my_plan, teammate_comp


def _smooth_hp(players, hp_hist, max_drop: int = 25) -> None:
    """Stabilise per-player HP across reads. Two corrections:
      - HP not read this frame (None) -> reuse that player's last known value;
      - an implausibly large single-frame drop (misread tiny digits, e.g. '89' -> '9') ->
        keep the last good value (you can't lose more than ~one combat, ~25, per round).
    Mutates players.
    """
    for p in players:
        name, hp = p.get("name"), p.get("hp")
        if not name:
            continue
        if hp is None:                     # not read this frame -> keep last known, if any
            if name in hp_hist:
                p["hp"] = hp_hist[name]
            continue
        if not isinstance(hp, int):
            continue
        prev = hp_hist.get(name)
        if prev is not None and hp < prev - max_drop:
            p["hp"] = prev                 # implausible crash -> keep last known HP
        else:
            hp_hist[name] = hp


# Contest detection now lives on the Ledger (ledger.contested_carries), which accumulates
# each player's carry across the whole game instead of relying on a single frame.


def _assemble_state(comp_key, my_comp, teammate_comp, partner_name, data, contested,
                    ledger: Ledger, stage: str = "unknown",
                    self_read: dict = None, owned_units=None,
                    traits=None, committed_comp=None, offered=None) -> dict:
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
        "offered": offered,                  # {kind, options:[{name,effect}]} when a pick is on screen
    }


def watch(poll: float = 0.5, settle: float = 0.4, min_gap: float = 1.5, shop_gap: float = 0.3,
          model: str = "gpt-4o", on_update=None,
          comp_key: str = None, partner_name: str = None, partner_comp_key: str = None,
          board: bool = False, augments: bool = False, shop: bool = False,
          offers: bool = False, items: bool = False, use_brain: bool = False,
          brain_gap: float = 18.0, local_eyes: bool = True, save_frames: int = 0,
          control: dict = None) -> None:
    """Watch the panel; read + coach when it changes and settles.

    use_brain — run the LLM reasoning brain (auto-off if no OPENAI_API_KEY); brain_gap
    throttles how often it's called (seconds) since each call costs tokens. Between
    calls the last plan is kept and fresh transient threats are layered on top.
    """
    purge_captures()
    atexit.register(purge_captures)
    coach = CoachRoland()
    ledger = Ledger()
    scout_det = ScoutDetector()         # left-panel != your comp -> you're scouting someone
    owned_tracker = PurchaseTracker()   # infers your bought units from shop diffs (no bench read)
    hit_tracker = HitTracker()          # copies-of-carry SEEN vs odds -> "you're not hitting"
    my_comp, my_plan, teammate_comp = _comp_context(comp_key, partner_name, partner_comp_key)
    partner_detail = compguide.comp_detail(partner_comp_key) if partner_comp_key else None
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
    pending_key = None                     # a DIFFERENT inferred comp awaiting confirmation
    pending_hits = 0
    SWITCH_CONFIRM = 3                     # inferred comp only flips after N reads agree (anti-jitter)
    hp_hist: dict = {}                     # per-player HP, to reject misread crashes
    last_valid_read = time.time()          # last time we saw a real lobby (>= 2 players)
    game_over_fired = False                # so we reset/blank only ONCE per real game-over
    GAME_OVER_GAP = 45.0                   # tolerate brief alt-tabs; only reset after this gap
    last_save = 0.0                        # for --save-frames training capture
    last_shop_sig = None                   # fast shop path: reroll change-detection
    last_shop_read = 0.0
    last_stage = None                      # reused by the fast shop path (stage changes slowly)
    last_contested = []                    # reused by the fast shop path (deny flags)
    last_hp = None                         # your own HP -> HP-aware "roll to stabilize" advice
    last_scout = None                      # most recent scouted opponent comp {owner,traits,stage}

    with mss.MSS() as sct:
        monitor = sct.monitors[1]
        try:
            while True:
                full = _grab_full(sct, monitor)
                sig = _signature(full)
                now = time.time()

                # Live comp override from the dashboard picker: when you declare your line
                # (or switch back to auto), lock it immediately instead of guessing from traits.
                if control is not None:
                    ck = control.get("comp_key")
                    if ck != comp_key:
                        comp_key = ck
                        my_comp, my_plan, teammate_comp = _comp_context(
                            comp_key, partner_name, partner_comp_key)
                        last_comp = compguide.comp_detail(comp_key) if comp_key else None
                        pending_key, pending_hits = None, 0

                if save_frames and (now - last_save) >= save_frames:   # training-data capture
                    try:
                        os.makedirs("training_frames", exist_ok=True)
                        full.save(os.path.join("training_frames", f"frame_{time.strftime('%H%M%S')}.jpg"),
                                  quality=88)
                        last_save = now
                    except Exception as e:
                        print(f"  (frame save failed: {e})")

                # --- Fast shop path -------------------------------------------------
                # The shop read is cheap (local OCR on the GPU) and the shop changes
                # every reroll, so read it on its OWN quick cadence and push a shop-only
                # update — decoupled from the heavier lobby/traits/board reads below, so
                # the shop keeps up with rerolls instead of waiting a full ~4-5s cycle.
                # The dashboard merges partial updates, so this doesn't clobber the lobby.
                if shop and local_eyes:
                    shop_sig = _signature_shop(full)
                    if _changed(last_shop_sig, shop_sig) and (now - last_shop_read) >= shop_gap:
                        last_shop_sig = shop_sig
                        last_shop_read = now
                        try:
                            sr = localvision.read_self_pil(full)
                        except Exception as e:
                            print(f"  (fast shop read failed: {e})")
                            sr = None
                        if sr:
                            shop_names = [s.get("name") for s in (sr.get("shop") or [])]
                            owned_tracker.update(shop_names, sr.get("gold"))
                            hit_tracker.update(shop_names)   # count copies-of-carry seen per roll
                            owned = list(owned_tracker.owned()) or None
                            sview = coach.shop_plan(sr.get("shop"), last_comp, sr.get("gold"),
                                                    partner_comp=partner_detail,
                                                    partner_name=partner_name, owned=owned,
                                                    contested=last_contested)
                            secon = coach.reroll_advice(sr.get("gold"), sr.get("level"),
                                                        (last_comp or {}).get("playstyle"),
                                                        stage=last_stage, hp=last_hp,
                                                        carry=(last_comp or {}).get("carry"))
                            if on_update:
                                on_update({"ts": time.strftime('%H:%M:%S'), "event": "shop",
                                           "shop": sview, "econ": (secon[0] if secon else None),
                                           "gold": sr.get("gold"), "level": sr.get("level")})
                        if not sr:
                            time.sleep(poll)
                        continue

                if _changed(last_sig, sig):
                    last_sig = sig
                    pending_since = now
                elif pending_since and (now - pending_since) >= settle and (now - last_read) >= min_gap:
                    pending_since = None
                    last_read = now
                    # In-game gate: a valid stage indicator ('4-6') means we're actually in
                    # a TFT game and not the client/desktop (friends list, news, clock). Read
                    # it first and reuse it for the timing advice below.
                    try:
                        stage_read = (localvision.read_stage_pil(full).get("stage")
                                      if local_eyes else None)
                    except Exception as e:
                        print(f"  (stage read failed: {e})")
                        stage_read = None
                    last_stage = stage_read or last_stage
                    try:
                        data = (localvision.read_lobby_pil(full) if local_eyes
                                else read_lobby_pil(full, model=model))
                    except Exception as e:
                        print(f"  (read failed: {e})")
                        time.sleep(poll)
                        continue

                    players = data.get("players") or []
                    if len(players) < 2 or (local_eyes and not localvision._valid_stage(stage_read)):
                        # Not in a game (client/desktop), or a loading/transition/combat frame.
                        # Don't reset on a brief absence; keep your last comp/advice shown. Only
                        # after a real gap (game actually ended) do we clear + blank, once.
                        if (now - last_valid_read) >= GAME_OVER_GAP and not game_over_fired:
                            coach.reset()
                            ledger.reset()
                            scout_det.reset()
                            last_scout = None
                            owned_tracker.reset()
                            hit_tracker.reset()
                            last_brain_recs = []
                            last_comp = compguide.comp_detail(comp_key) if comp_key else None
                            hp_hist.clear()
                            game_over_fired = True
                            removed = purge_captures()
                            if on_update:
                                on_update({"ts": time.strftime('%H:%M:%S'), "event": "game_over",
                                           "data": None, "advice": [], "positioning": [], "comp": None,
                                           "shop": [], "econ": None, "items": [], "bench": [],
                                           "stage": None, "contested": [], "traits": [],
                                           "gold": None, "level": None})
                            else:
                                print(f"[{time.strftime('%H:%M:%S')}] Game over — cleared session "
                                      f"memory; removed {removed} temp file(s).\n")
                        time.sleep(poll)
                        continue

                    last_valid_read = now                      # real lobby on screen -> game is live
                    game_over_fired = False
                    _smooth_hp(players, hp_hist)               # correct misread HP before anyone uses it
                    my_hp = next((p.get("hp") for p in players if p.get("is_self")), None)
                    if my_hp is not None:
                        last_hp = my_hp                        # cache for the fast shop path's econ
                    coach.observe(data)                        # keep session tracking; output dropped (HP reads too noisy)
                    for p in players:                          # ledger: remember spiked carries
                        if p.get("unit") and p.get("name"):
                            ledger.note_carry(p["name"], p["unit"], stage=stage_read)
                    contested = ledger.contested_carries()   # accumulated across the game
                    last_contested = contested                # reused by the fast shop path (deny flags)
                    open_list = compguide.open_comps(contested)
                    alt_name = open_list[0]["name"] if open_list else "an open line"

                    augs = []
                    if augments:
                        try:
                            augs = (localvision.read_augments_pil(full) if local_eyes
                                    else read_augments_pil(full, model=model)).get("augments", [])
                            ledger.note_augments(SELF, augs)
                        except Exception as e:
                            print(f"  (augment read failed: {e})")

                    self_read = None
                    if shop:
                        try:
                            self_read = (localvision.read_self_pil(full) if local_eyes
                                         else read_self_pil(full, model=TEXT_MODEL))
                        except Exception as e:
                            print(f"  (shop read failed: {e})")
                    if self_read:                          # infer purchases from shop diffs
                        sr_names = [s.get("name") for s in (self_read.get("shop") or [])]
                        owned_tracker.update(sr_names, self_read.get("gold"))
                        hit_tracker.update(sr_names)       # count copies-of-carry seen per roll

                    # Traits = ground truth for which comp you're building -> read whenever the
                    # brain is on, so the comp pick is grounded in YOUR board, not random.
                    traits_read = None
                    if brain_on or local_eyes:        # free when local_eyes; grounds the comp pick
                        try:
                            traits_read = (localvision.read_traits_pil(full) if local_eyes
                                           else read_traits_pil(full, model=TEXT_MODEL)).get("traits")
                        except Exception as e:
                            print(f"  (trait read failed: {e})")

                    # SCOUT DETECTION: if the left trait panel doesn't match YOUR comp, you're
                    # viewing an opponent's board. Two effects: (1) attribute the read to that
                    # opponent (their comp -> counter advice), NOT to yourself; (2) don't let a
                    # foreign panel corrupt your own comp inference/advice this frame.
                    if traits_read:
                        tag, _ov = scout_det.classify(traits_read, last_comp)
                        if tag == "scout":
                            # "who" needs the scoreboard-highlight read (calibration pending); until
                            # then attribute to next_opponent if known, else leave unnamed.
                            owner = data.get("next_opponent")
                            last_scout = {"owner": owner, "traits": traits_read, "stage": stage_read}
                            if owner:
                                ledger.note_comp(owner, traits_read, stage=stage_read)
                            traits_read = None   # not YOUR panel -> keep it out of your-comp logic


                    # Bench tiles are icons (recognition unreliable), so "what you own" is INFERRED
                    # from shop diffs (PurchaseTracker): units that left the shop while the rest
                    # stayed = bought. Approximate (drifts on sells/combines/cannon) but free and no
                    # vision. This powers "pairs with a unit you own" without reading the bench.
                    owned_units, bench_view = list(owned_tracker.owned()), []

                    # Board read adds on-board units + positioning (paid; bench already covered above).
                    positioning = []
                    if board:
                        try:
                            board_read = read_board_pil(full, model=model)
                            positioning = coach.positioning(board_read)
                            owned_units += [u.get("name") for u in (board_read.get("units") or [])
                                            if u.get("name")]
                            owned_units += [b for b in (board_read.get("bench") or []) if b]
                        except Exception as e:
                            print(f"  (board read failed: {e})")
                    owned_units = owned_units or None

                    # A live God/augment pick on screen -> advise immediately (skip throttle).
                    offered = None
                    if offers:
                        try:
                            o = (localvision.read_offer_pil(full) if local_eyes
                                 else read_offer_pil(full, model=TEXT_MODEL))
                            if o.get("options"):
                                offered = o
                        except Exception as e:
                            print(f"  (offer read failed: {e})")

                    if brain_on:
                        if offered or (now - last_brain) >= brain_gap:
                            last_brain = now
                            try:
                                state = _assemble_state(
                                    comp_key, my_comp, teammate_comp, partner_name, data,
                                    contested, ledger, stage=(stage_read or "unknown"),
                                    self_read=self_read, owned_units=owned_units,
                                    traits=traits_read, offered=offered,
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
                        rc, rp = my_comp, my_plan
                        if not comp_key:
                            det = (compguide.suggest_for_traits(traits_read, contested,
                                   current_key=(last_comp or {}).get("key")) if traits_read else None)
                            if det:
                                cand_key = next((k for k, v in compguide.COMPS.items() if v is det), None)
                                cur_key = (last_comp or {}).get("key")
                                if last_comp is None or cand_key == cur_key:
                                    last_comp = compguide.comp_detail(cand_key) or last_comp
                                    pending_key, pending_hits = None, 0     # steady -> clear candidate
                                else:
                                    # a DIFFERENT comp this frame. Don't flip on OCR jitter (e.g. the
                                    # anchor trait misread by 1 with several traits tied) — require it
                                    # to win SWITCH_CONFIRM reads in a row before actually switching.
                                    pending_hits = pending_hits + 1 if cand_key == pending_key else 1
                                    pending_key = cand_key
                                    if pending_hits >= SWITCH_CONFIRM:
                                        last_comp = compguide.comp_detail(cand_key) or last_comp
                                        pending_key, pending_hits = None, 0
                                # advise the HELD comp (unchanged unless a switch was confirmed above)
                                rc, rp = _comp_dicts(compguide.COMPS.get((last_comp or {}).get("key")))
                            elif last_comp and last_comp.get("key"):
                                # no trait read this frame (combat/transition/choice screen) -> keep
                                # advising your COMMITTED comp; don't fall back to generic "open lines"
                                rc, rp = _comp_dicts(compguide.COMPS.get(last_comp["key"]))
                        hit_report = hit_tracker.report((rc or {}).get("carry"),
                                                        (self_read or {}).get("level"))
                        strategic = _rules_advice(coach, rc, rp, teammate_comp,
                                                  data, contested, augs, alt_name,
                                                  stage=stage_read, level=(self_read or {}).get("level"),
                                                  traits=traits_read,
                                                  rivals=ledger.players_on((rc or {}).get("carry")),
                                                  scouted=set(ledger.carries),
                                                  stale=set(ledger.stale_reads(stage_read)),
                                                  hp=my_hp, gold=(self_read or {}).get("gold"),
                                                  ledger=ledger, last_scout=last_scout,
                                                  hit_report=hit_report)

                    recs = strategic        # brain (or rules) only — no noisy per-read HP alerts
                    # Free God-choice pick: the brain handles offers itself, so only inject here
                    # when running the rules coach (brain off). Pins to top via ACTIVE_CHOICE.
                    if not brain_on and offered and offered.get("kind") == "god" and offered.get("options"):
                        recs = coach.choose_god(offered["options"],
                                                (last_comp or {}).get("playstyle") or "flex") + recs
                    if not brain_on and augs and not offered:   # augment screen (not the God screen)
                        recs = coach.choose_augment(augs, stage=stage_read,
                                                    traits=[t.get("name") for t in (traits_read or [])]) + recs
                    if last_comp and owned_units:    # shopping list from inferred-owned units
                        recs = recs + coach.comp_progress(last_comp, owned_units, traits=traits_read)

                    shop_view = (coach.shop_plan(self_read.get("shop"), last_comp,
                                                 self_read.get("gold"), partner_comp=partner_detail,
                                                 partner_name=partner_name, owned=owned_units,
                                                 contested=contested)
                                 if self_read else [])
                    item_view = []
                    if items and last_comp:
                        try:
                            offered_items = localvision.read_items_pil(full).get("items") or []
                            if offered_items:
                                item_view = coach.item_choice(offered_items, last_comp)
                        except Exception as e:
                            print(f"  (item read failed: {e})")
                    econ = (coach.reroll_advice(self_read.get("gold"), self_read.get("level"),
                                                (last_comp or {}).get("playstyle"), stage=stage_read,
                                                hp=my_hp, carry=(last_comp or {}).get("carry"))
                            if self_read else [])
                    stamp = time.strftime('%H:%M:%S')
                    if on_update:
                        # per-carry rival counts (opponents seen on each carry) -> the picker
                        # flags which lines are open vs contested so you lock the right one.
                        carry_counts = {}
                        for c in ledger.carries.values():
                            if c:
                                carry_counts[c.lower()] = carry_counts.get(c.lower(), 0) + 1
                        on_update({"ts": stamp, "event": "read", "data": data,
                                   "advice": recs, "positioning": positioning, "comp": last_comp,
                                   "shop": shop_view, "econ": (econ[0] if econ else None),
                                   "items": item_view, "bench": bench_view, "stage": stage_read,
                                   "contested": contested, "traits": traits_read,
                                   "gold": (self_read or {}).get("gold"),
                                   "level": (self_read or {}).get("level"),
                                   "carry_counts": carry_counts})
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
    p.add_argument("--board", action="store_true", help="also read your board for positioning (PAID gpt-4o — positioning isn't free yet)")
    p.add_argument("--augments", action="store_true", help="also read your augment choices (free, local icon match)")
    p.add_argument("--shop", action="store_true", help="also read your shop/gold/level -> 'buy this' advice (free, local)")
    p.add_argument("--offers", action="store_true", help="also read the God-choice screen -> which God to take (free, local OCR)")
    p.add_argument("--items", action="store_true", help="also read the item-choice screen -> highlight carry items (free, local)")
    p.add_argument("--brain", action="store_true", help="opt in to the PAID gpt-4o reasoning brain (needs OPENAI_API_KEY + credits); default is the free rules coach")
    p.add_argument("--rules-only", action="store_true", help="(deprecated — the free rules coach is the default now)")
    p.add_argument("--llm-eyes", action="store_true", help="use the paid gpt-4o lobby reader instead of free local OCR")
    p.add_argument("--save-frames", type=int, default=0, metavar="SECS",
                   help="save a full screenshot every SECS to training_frames/ — build a real dataset to train icon recognition (bench/items/augments)")
    return p


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    args = _build_parser().parse_args()
    if args.once:
        _once()
    else:
        watch(comp_key=args.comp, partner_name=args.partner, partner_comp_key=args.partner_comp,
              board=args.board, augments=args.augments, shop=args.shop, offers=args.offers,
              items=args.items, use_brain=args.brain, local_eyes=not args.llm_eyes,
              save_frames=args.save_frames)

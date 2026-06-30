"""Coach Roland — turns lobby/board reads into structured, explained advice.

Every recommendation is a dict:
    {"text": short call, "why": the reasoning (tooltip), "stat": optional data
     backing or None, "severity": "danger" | "warn" | "info"}

Tracks a small in-memory history of THIS game's reads (structured data only, no
images) to spot what changed. reset() wipes it between games so nothing piles up.
"""

from collections import Counter

from . import cdragon, compguide

NAME = "Coach Roland"
_MAX_HISTORY = 40

# Priority tiers. Higher floats to the top of the advice list. ACTIVE_CHOICE is for
# time-boxed in-game decisions (the 2 Gods, the 3 augments) — they have a ~30s clock,
# so they must sit above passive/standing advice and be visually loud.
ACTIVE_CHOICE = 100

# God preference by playstyle (which of the 2 offered to favor).
_GOD_PREF = {
    "fast9": ["Soraka", "Ahri", "Kayle", "Ekko", "Aurelion Sol", "Varus", "Yasuo", "Evelynn", "Thresh"],
    "reroll": ["Kayle", "Ahri", "Ekko", "Soraka", "Varus", "Yasuo", "Aurelion Sol", "Evelynn", "Thresh"],
    "flex": ["Kayle", "Ahri", "Ekko", "Soraka", "Aurelion Sol", "Varus", "Yasuo", "Evelynn", "Thresh"],
}


def _rec(text, why, severity="info", stat=None, priority=0, timer=None):
    """priority: higher pins to the top (see ACTIVE_CHOICE). timer: seconds on the
    clock for a time-boxed choice, surfaced as a countdown badge (None = no clock)."""
    return {"text": text, "why": why, "severity": severity, "stat": stat,
            "priority": priority, "timer": timer}


# Augments whose value is generic/econ/combat transfer when you pivot; ones named
# after a unit/trait are "locked" to that line. Heuristic until we have augment data.
_GENERIC_AUG_HINTS = ("econ", "gold", "income", "experience", "level", "component",
                       "grab bag", "pandora", "built different", "cluttered", "tome",
                       "loot", "thrifty", "salvage", "training")


class CoachRoland:
    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self._prev = {}
        self._prev_next = None
        self._log = []

    # ---- lobby coaching ------------------------------------------------------
    def observe(self, data: dict) -> list[dict]:
        players = data.get("players", []) or []
        out: list[dict] = []
        cur = {}

        for p in players:
            name = p.get("name") or "YOU"
            unit, stars, hp = p.get("unit"), p.get("stars") or 0, p.get("hp")
            cur[name] = {"unit": unit, "stars": stars, "hp": hp}
            prev = self._prev.get(name)
            spiked = unit and (prev is None or prev.get("unit") != unit
                               or (prev.get("stars") or 0) < stars)
            if spiked and name != "YOU":
                pips = "*" * (stars or 1)
                out.append(_rec(
                    f"{name} hit {unit} {pips}",
                    f"{name} just upgraded {unit}, so copies of it are leaving the shared pool. "
                    f"If you're also building {unit}, your odds of hitting it just dropped — "
                    f"contest only if you're ahead, otherwise look elsewhere.",
                    "warn"))

        for p in sorted((p for p in players if isinstance(p.get("hp"), int) and p["hp"] <= 20),
                        key=lambda x: x["hp"]):
            who = p.get("name") or "YOU"
            holds = p.get("holds")  # units they're sitting on (needs a board read)
            if holds:
                out.append(_rec(
                    f"{who} ({p['hp']} HP) holds {', '.join(holds)}",
                    f"{who} is about to die. When they bust, {', '.join(holds)} return to the shared "
                    f"pool. If any of those are in your comp, DON'T roll now — wait for them to die, "
                    f"then roll into the fuller pool so you actually hit.",
                    "warn"))
            else:
                out.append(_rec(
                    f"{who} is on {p['hp']} HP",
                    f"When {who} dies, the units they're holding return to the shared pool — pieces "
                    f"you want can free up. Have gold ready to roll right after they go.",
                    "warn"))

        nxt = data.get("next_opponent")
        if nxt and nxt != self._prev_next:
            out.append(_rec(
                f"You fight {nxt} next",
                f"Scout {nxt}'s board now: position your carry away from their threats and "
                f"check if a defensive item swap helps for this specific fight.",
                "info"))

        if sum(1 for p in players if p.get("unit")) >= 3:
            out.append(_rec(
                "Multiple boards are spiking",
                "Several opponents powered up at once. If your board can't hold a fight right now, "
                "you'll bleed out fast — strengthen the board before you greed for econ.",
                "warn"))

        self._prev, self._prev_next = cur, nxt
        self._log.append(data)
        if len(self._log) > _MAX_HISTORY:
            self._log.pop(0)
        return out

    # ---- contested-pivot engine (the "never hard-switch" fix) -----------------
    def contested_pivot(self, my_comp: dict, data: dict, augments=None,
                        alt_comp: str = "an open line", threshold: int = 2) -> list[dict]:
        """If 2+ players share your carry, push a pivot — weighed against your augments."""
        my_carries = [c.lower() for c in (my_comp or {}).get("carries", [])]
        if not my_carries:
            return []
        players = data.get("players", []) or []
        contesters = sorted({
            p.get("name") for p in players
            if p.get("unit") and p["unit"].lower() in my_carries and not p.get("is_self")
        } - {None})
        if len(contesters) < threshold:
            return []

        augments = augments or []
        carry = (my_comp.get("carries") or ["your carry"])[0]
        keep, locked = [], []
        for a in augments:
            al = a.lower()
            if any(h in al for h in _GENERIC_AUG_HINTS) and carry.lower() not in al:
                keep.append(a)
            else:
                locked.append(a)

        aug_note = ""
        if augments:
            aug_note = (f" Your augments mostly transfer ({', '.join(keep)} carry over; "
                        f"only {', '.join(locked) or 'none'} is stuck) — so switching is cheap."
                        if len(keep) >= len(locked) else
                        f" Careful: your augments are tied to this line "
                        f"({', '.join(locked)}) — staying may be right despite the contest.")

        severity = "danger" if len(keep) >= len(locked) else "warn"
        return [_rec(
            f"PIVOT — {len(contesters)} players contest {carry}",
            f"{', '.join(contesters)} are on {carry} too. The pool can't feed all of you, "
            f"so you'll be starved and place low if you stay.{aug_note} Consider {alt_comp}.",
            severity,
            stat=None)]  # kept qualitative on purpose — no live win-rates/placements (Riot TFT policy)

    # ---- Double Up (primary mode) -------------------------------------------
    def doubleup(self, my_comp: dict, teammate_comp: dict, data: dict,
                 augments=None, alt_comp: str = "an open line") -> list[dict]:
        """Team-of-2 advice: don't contest your partner; cover/counter as a team.

        Double Up shares one unit pool across all 8 players. The biggest leak is
        you and your partner forcing the same carry — you starve each other.
        """
        recs: list[dict] = []
        mine = [c.lower() for c in (my_comp or {}).get("carries", [])]
        mate = [c.lower() for c in (teammate_comp or {}).get("carries", [])]
        partner = (teammate_comp or {}).get("name")

        # 1. Partner contest — the cardinal Double Up sin
        overlap = sorted(set(mine) & set(mate))
        if overlap:
            u = overlap[0].title()
            recs.append(_rec(
                f"You and your partner both want {u}",
                f"Double Up shares ONE unit pool across all 8 players, so you and your partner are "
                f"fighting each other for {u} copies — you'll both end up under-3-starred. Whoever's "
                f"further along keeps {u}; the other pivots to {alt_comp}. Don't split the carry.",
                "danger"))

        # 2. Cross-team contest (other 6, partner excluded — you can reinforce them, not contest)
        players = data.get("players", []) or []
        contesters = sorted({
            p.get("name") for p in players
            if p.get("unit") and p["unit"].lower() in mine
            and not p.get("is_self") and p.get("name") != partner
        } - {None})
        carry = (my_comp.get("carries") or ["your carry"])[0]
        if len(contesters) >= 2:
            recs.append(_rec(
                f"{len(contesters)} enemies also on {carry}",
                f"{', '.join(contesters)} are contesting {carry} across the other teams. This "
                f"contested, it's often better to shift to {alt_comp} the lobby is leaving open "
                f"and let your partner anchor the damage.",
                "warn"))
            recs.append(_rec(
                f"Tell {partner or 'your partner'}: reinforce me {carry}",
                f"Message {partner or 'your partner'} now — ask them to buy spare {carry} copies and "
                f"send them to you. Pooling both your shop odds is how a team out-rolls a contest in "
                f"Double Up.",
                "info"))

        # 3. Team coverage nudge — complement, don't mirror
        if mate and not overlap:
            recs.append(_rec(
                f"Your partner anchors {(teammate_comp.get('carries') or ['their line'])[0]}",
                f"You're not contesting each other — good. Build a comp that covers what they don't "
                f"(different damage type / a frontline if they're squishy) so your team beats more "
                f"matchups together.",
                "info"))
        return recs

    # ---- positioning (experimental) ------------------------------------------
    def positioning(self, board: dict) -> list[dict]:
        units = (board or {}).get("units", []) or []
        out = []
        for u in units:
            role, row, side = u.get("role"), u.get("row"), u.get("side")
            name = u.get("name", "a unit")
            if role in ("tank", "bruiser") and row in ("mid", "back"):
                out.append(_rec(
                    f"Move {name} to the front",
                    f"{name} is a frontline unit but it's sitting in the {row}. It needs to be up "
                    f"front to absorb damage and protect your carries; right now they're exposed.",
                    "warn"))
            if role == "carry" and not (row == "back" and side in ("left", "right")):
                out.append(_rec(
                    f"Put {name} in a back corner",
                    f"{name} is your carry — tuck it into a back corner so assassins and divers "
                    f"take longest to reach it, buying it more time to deal damage.",
                    "warn"))
            if role in ("caster", "support") and row == "front":
                out.append(_rec(
                    f"Pull {name} back",
                    f"{name} is squishy and shouldn't be on the front line — it'll die before it "
                    f"does anything. Move it behind your frontline.",
                    "info"))
        return out

    # ---- early-game bridge + buy priority ------------------------------------
    def early_game(self, plan: dict) -> list[dict]:
        """plan = {name, carry, early:[holders], level_plan} -> an IMPORTANT buy rec.

        Solves "I know my level-8 comp but not what to play before it." The holder
        list comes from comp-guide data (a meta source).
        """
        early = (plan or {}).get("early_units") or (plan or {}).get("early")
        if not early:
            return []
        holders = ", ".join(early)
        return [_rec(
            f"EARLY: bridge to {plan.get('carry', 'your carry')} with {holders}",
            f"Your endgame is {plan.get('name', 'your comp')}, built around {plan.get('carry', 'a late carry')} "
            f"that mostly comes online at level 8. You won't survive waiting for it — until then, hold and "
            f"play {holders}. {plan.get('level_plan', 'Slam early items, stay healthy, then roll at 8.')}",
            "buy",
            stat=plan.get("source"))]

    def teammate_buy(self, partner: str, unit: str, copies_left: int = 1) -> dict:
        """Alert to buy a unit for your partner via the Teamwork Cannon."""
        return _rec(
            f"BUY {unit} -> cannon to {partner or 'partner'}",
            f"{partner or 'Your partner'} is {copies_left} copy from upgrading {unit}. Buy any {unit} "
            f"you see and send it over the Teamwork Cannon — finishing their upgrade now is worth more "
            f"than holding your gold.",
            "buy")

    def item_plan(self, comp: dict, contested: bool = False, alt: str = "an open carry") -> list[dict]:
        """Items for your main carry — or, if contested, hold flexible and stay pivot-ready."""
        if not comp:
            return []
        carry = comp.get("carry", "your carry")
        if not contested:
            items = ", ".join(comp.get("carry_items", []))
            cost = cdragon.cost_of(carry) or 0
            playstyle = (comp.get("playstyle") or "").lower()
            if cost >= 4 or playstyle in ("fast8", "fast9"):
                target = (f"{carry} is a {cost}-cost — you play it 1-2 star WITH ITEMS; you won't "
                          f"3-star (\"gold\") a {cost}-cost, so buy copies toward 2-star and to deny, "
                          f"don't chase a gold.")
            elif playstyle == "reroll" or (0 < cost <= 2):
                target = (f"{carry} is a reroll carry — slow-roll and collect copies for a 3-star "
                          f"(\"gold\"); that's your power spike.")
            else:
                target = f"Aim to 2-star {carry} and itemize."
            return [_rec(
                f"Build {carry}'s items: {items}",
                f"{target} Best build is {items} — collect the components from carousels and item "
                f"drops and slam toward it.",
                "buy", stat=comp.get("source"))]
        flex = ", ".join(comp.get("flexible_components", comp.get("carry_components", [])))
        return [_rec(
            f"Hold {carry}'s items — they're contested",
            f"{carry} is contested, so you may not hit. DON'T lock their items yet. Build flexible "
            f"components ({flex} slot onto many carries) and stay ready to move them onto {alt} if you pivot.",
            "warn")]

    def contest_advice(self, unit: str, n_teams: int, partner: str = None) -> list[dict]:
        """Heavy contest -> don't roll to gold it; deny + hold within your team (bench-aware)."""
        if not unit or n_teams < 2:
            return []
        keep = (f" Grab copies to deny them and keep them in your team — hold the key ones on your bench "
                f"or cannon spares to {partner}" if partner else
                " Grab copies to deny them and hold the key ones on your bench")
        return [_rec(
            f"{n_teams} teams contest {unit} — don't gold it",
            f"With {n_teams} teams on {unit}, the shared pool won't 3-star you — burning gold chasing it "
            f"is a trap.{keep}. Bench space is limited, so only hold what actually matters.",
            "warn")]

    # ---- counter-aware recommendation (NEVER assume; always read the lobby) ---
    def recommend(self, contested_carries: list[str], my_intended: str = None,
                  top: int = 3) -> list[dict]:
        """Suggest open comps — but only when it's useful. If you've already committed to a
        comp and it's NOT contested, stay quiet: listing other lines just reads as 'switch'."""
        recs: list[dict] = []
        if my_intended:
            if my_intended.lower() in {c.lower() for c in (contested_carries or [])}:
                recs += self.discourage(my_intended)     # your line IS contested -> warn + show alts
            else:
                return recs                               # committed + uncontested -> no distractions
        opts = compguide.open_comps(contested_carries)[:top]
        if not opts:
            recs.append(_rec(
                "Everything strong is contested",
                "The whole lobby is fighting over the top lines — play flex, take the best units "
                "you're offered, and win on tempo and positioning rather than forcing a contested comp.",
                "warn"))
            return recs
        names = " / ".join(c["name"] for c in opts)
        recs.append(_rec(
            f"Open lines: {names}",
            "These are open in your lobby right now — nobody's heavy on them. (Recommendations are "
            "always gated on what others are playing; never force into a contest.)",
            "info", stat=opts[0].get("source")))
        return recs

    def discourage(self, carry: str, n_teams: int = None) -> list[dict]:
        """Explicit 'do NOT go this' — active discouragement, not just omission."""
        who = f"{n_teams} teams are" if n_teams else "Multiple teams are"
        return [_rec(
            f"AVOID forcing {carry}",
            f"{who} on {carry}. I strongly suggest you do NOT go it — the shared pool can't feed you, "
            f"you'll be starved and bottom out. Take an open line instead.",
            "danger")]

    def counter_for(self, threat: str) -> list[dict]:
        """Positional/item counter for a scouted opponent threat (assassins, heavy_frontline, ...)."""
        tip = compguide.COUNTER_DYNAMICS.get((threat or "").lower())
        if not tip:
            return []
        return [_rec(f"Counter the {threat.replace('_', ' ')} you fight next", tip, "info")]

    # ---- in-game choices: Gods (2 offered) + augments (3 offered) -------------
    def choose_god(self, offered: list[str], playstyle: str = "flex") -> list[dict]:
        """Pick the better of the 2 offered Gods for your comp's playstyle."""
        if not offered:
            return []
        pref = _GOD_PREF.get(playstyle, _GOD_PREF["flex"])
        pick = sorted(offered, key=lambda g: pref.index(g) if g in pref else 99)[0]
        info = compguide.GODS.get(pick, {})
        return [_rec(
            f"God: take {pick}",
            f"For your {playstyle} comp, {pick} is the better of the two — {info.get('note', '')} "
            f"({info.get('variance', '?')}-variance).",
            "buy", priority=ACTIVE_CHOICE, timer=30)]

    def choose_augment(self, offered: list[str], stage: str = None, traits=None) -> list[dict]:
        """Rank the 3 offered augments. Exact win-% needs live augment-stat data."""
        if not offered:
            return []
        traits = [t.lower() for t in (traits or [])]

        def score(a):
            al, s = a.lower(), 0
            if "emblem" in al and any(t in al for t in traits):
                s += 3                                   # emblem that points your comp
            if a in compguide.TOP_AUGMENTS:
                s += 2                                   # proven strong this patch
            if stage and str(stage).startswith("2") and any(k in al for k in
                                                            ("loan", "gold", "income", "econ")):
                s += 1                                   # econ first on 2-1
            return s

        pick = sorted(offered, key=score, reverse=True)[0]
        return [_rec(
            f"Augment: take {pick}",
            "Best of the three for your board. Rule of thumb: an emblem that points your comp > a "
            "proven strong augment > econ early / combat later. (Live win-rates/placements are "
            "intentionally not shown — Riot's TFT policy prohibits it; save stat review for post-game.)",
            "buy", stat=None,
            priority=ACTIVE_CHOICE, timer=30)]

    def shop_advice(self, shop, comp) -> list[dict]:
        """Quick wins: units sitting in your shop RIGHT NOW that belong in your comp."""
        if not shop or not comp:
            return []
        carry = (comp.get("carry") or "").lower()
        units = {u.lower() for u in (comp.get("early_units") or [])}
        units |= {u.lower() for u in (comp.get("board") or comp.get("final_board") or [])}
        out = []
        for slot in shop:
            n = (slot or {}).get("name") or ""
            nl = n.lower()
            if not n:
                continue
            if nl == carry:
                out.append(_rec(f"BUY {n} now — your carry",
                                f"{n} is your main carry. Grab every copy you can find to upgrade it sooner.",
                                "buy"))
            elif nl in units:
                out.append(_rec(f"BUY {n} — fits your comp",
                                f"{n} is part of {comp.get('name', 'your comp')}. Pick it up while it's in your shop.",
                                "buy"))
        return out

    def shop_plan(self, shop, comp, gold=None, partner_comp=None, partner_name=None,
                  owned=None) -> list[dict]:
        """Per-slot shop view for the dashboard strip — Double-Up + pair aware.

        action: buy  = you want it (a PAIR you're collecting, or in your comp), affordable
                lock = you want it but you're short on gold -> lock the shop to keep it
                give = your PARTNER needs it -> buy and cannon it to them
                None = nobody needs it (dim)
        A "pair" (you already own a copy, or the same unit shows up twice in this shop) is a
        top early-game buy regardless of comp. Your own needs outrank your partner's.
        """
        if not shop:
            return []

        def unit_set(c):
            if not c:
                return set(), ""
            u = {x.lower() for x in (c.get("early_units") or [])}
            u |= {x.lower() for x in (c.get("board") or c.get("final_board") or [])}
            return u, (c.get("carry") or "").lower()

        my_units, my_carry = unit_set(comp)
        p_units, p_carry = unit_set(partner_comp)
        comp_primary = ((comp.get("traits") or [None])[0] or "").lower() if comp else ""
        # owned = your 1-star copies (a unit already 2★ isn't a pair to collect). Each copy
        # is one list entry, so Counter gives true copy counts.
        owned_counts = Counter(o.lower() for o in (owned or []))
        shop_counts = Counter((s or {}).get("name", "").lower() for s in shop if s and s.get("name"))

        view = []
        for s in shop:
            name = (s or {}).get("name") or None
            cost = (s or {}).get("cost")
            nl = (name or "").lower()
            affordable = gold is None or cost is None or gold >= cost
            is_my_carry = bool(name) and nl == my_carry
            mine = bool(name) and (is_my_carry or nl in my_units)
            # copies you'd hold if you bought the shop copies of this unit. 3 copies = a 2★.
            copies = owned_counts[nl] + shop_counts[nl]
            already_two_star = owned_counts[nl] >= 3   # already merged a 2★ -> not a pair to chase
            # Only chase a pair if the unit is IN your comp (or you haven't committed to one
            # yet). Don't tell a committed Space Groove player to buy Lissandra just because
            # they happen to hold a copy — off-comp pairs are a trap once you have a plan.
            pair = bool(name) and copies >= 2 and (mine or not comp) and not already_two_star
            tostar = ("makes 2★" if copies >= 3 else f"{copies}/3 to 2★") if pair else None
            theirs = bool(name) and not mine and not pair and partner_comp and (nl == p_carry or nl in p_units)
            action, who = None, None
            if mine or pair:
                action, who = ("buy" if affordable else "lock"), "you"
            elif theirs:
                action, who = ("give" if affordable else None), "partner"
            # WHY this unit: your carry / a trait piece for your comp / a frontline body in
            # the comp / a pair you're collecting / your partner's.
            if is_my_carry:
                role = "carry"
            elif mine:
                utraits = {t.lower() for t in cdragon.champ_traits(name)}
                role = "core" if comp_primary and comp_primary in utraits else "body"
            elif pair:
                role = "pair"
            elif theirs:
                role = "partner"
            else:
                role = None
            view.append({"name": name, "cost": cost, "action": action, "carry": is_my_carry,
                         "pair": pair, "tostar": tostar, "for": who, "role": role,
                         "partner": partner_name if theirs else None})

        # Gold-budget sequencing: with limited gold, keep the highest-priority buys you can
        # actually afford in order; downgrade the rest to lock (yours) / skip (partner's).
        if gold is not None:
            def _prio(v):
                return 0 if v["carry"] else (1 if v["pair"] else (2 if v["for"] == "you" else 3))
            remaining = gold
            for v in sorted((x for x in view if x["action"] in ("buy", "give")),
                            key=lambda x: (_prio(x), x["cost"] if x["cost"] is not None else 99)):
                c = v["cost"]
                if c is not None and c <= remaining:
                    remaining -= c
                else:
                    v["action"] = "lock" if v["for"] == "you" else None
        return view

    def reroll_advice(self, gold, level, playstyle, stage=None) -> list[dict]:
        """When to reroll vs level vs save — from gold + level + playstyle, tuned by stage."""
        if gold is None:
            return []
        act = None
        if stage:
            try:
                act = int(str(stage).split("-")[0])
            except Exception:
                act = None
        early = act is not None and act <= 2     # stage 1-x / 2-x = econ phase, not roll phase

        if playstyle == "reroll":
            if level and level >= 6 and gold >= 50:
                return [_rec("Slow-roll now",
                             f"Level {level}, {gold} gold. Reroll a little each round but stay above ~50 gold, "
                             f"to find your upgrades while keeping interest. Don't level past your carry's breakpoint.",
                             "buy")]
            tail = f" You're at stage {stage} — hit your econ breakpoints first." if early else \
                   " Don't roll under 50 unless you're low on HP."
            return [_rec("Build to 50 gold, then roll",
                         "Reroll comp: get to 50 gold first for max interest, then slow-roll." + tail, "info")]
        if gold >= 50:
            return [_rec("Level up, don't roll",
                         f"Fast-leveling comp at {gold} gold — press Buy XP to push your level, and save your roll "
                         f"for level 8.", "buy")]
        if early:
            return [_rec("Too early to roll — build econ + board",
                         f"Stage {stage}: don't spend gold rolling. Buy XP on curve, grab pairs, hold for interest, "
                         f"and play your strongest board. Roll once you hit level 8 (around stage 4-1).", "info")]
        return [_rec("Save and build econ",
                     "Hold toward 50 gold for interest; play your strongest board and slam item pieces. Roll at "
                     "level 8 (around stage 4-1).", "info")]

    def comp_progress(self, comp, owned) -> list[dict]:
        """Shopping list: which of your comp's core units you have (inferred) vs still need.
        Complements the shop strip — that shows what's available now; this shows the goal."""
        if not comp:
            return []
        board = comp.get("board") or comp.get("final_board") or comp.get("early_units") or []
        if not board:
            return []
        have = {o.lower() for o in (owned or [])}
        got = [u for u in board if u.lower() in have]
        need = [u for u in board if u.lower() not in have]
        name = comp.get("name") or "your comp"
        if not need:
            return [_rec(f"Core board complete ({len(got)}/{len(board)})",
                         f"You've got every core unit for {name} — now focus on upgrades (2★/3★), "
                         f"items, and positioning.", "info")]
        return [_rec(f"Comp progress {len(got)}/{len(board)} — hunt {', '.join(need[:4])}",
                     f"For {name}: have {', '.join(got) or 'none yet'}. Still need {', '.join(need)}. "
                     f"Prioritize these in shops and rolls.", "info")]

    def trait_advice(self, traits, max_recs=2) -> list[dict]:
        """Flag active traits that are ONE unit from their next breakpoint — a power spike
        you can often grab cheaply. Uses your live trait counts + CDragon breakpoints."""
        if not traits:
            return []
        near = []
        for t in traits:
            name, count = t.get("name"), t.get("count")
            if not name or count is None:
                continue
            nxt = next((b for b in cdragon.trait_breakpoints(name) if b > count), None)
            if nxt is not None and nxt - count == 1:        # exactly one unit away
                near.append((nxt, name, count))
        near.sort(key=lambda x: -x[0])                       # bigger breakpoints first
        return [_rec(f"1 unit from {name} {nxt}",
                     f"You have {count} {name}; one more {name} unit hits the {nxt} breakpoint. "
                     f"If one fits your board, it's a cheap power spike.", "info")
                for nxt, name, count in near[:max_recs]]

    def level_pacing(self, stage, level, playstyle=None) -> list[dict]:
        """Compare your level to standard pacing for the stage. Reroll comps level on
        their own schedule, so this only nudges fast / flex / standard lines."""
        if not stage or level is None or (playstyle or "").lower() == "reroll":
            return []
        try:
            act, rnd = (int(x) for x in str(stage).split("-")[:2])
        except Exception:
            return []
        pacing = {2: (4, 5), 3: (6, 6), 4: (7, 8), 5: (8, 8), 6: (9, 9), 7: (9, 9)}
        if act not in pacing:        # stage 1 is auto-leveled; nothing to nudge
            return []
        early, late = pacing[act]
        tgt = early if rnd < 5 else late
        if level < tgt:
            return [_rec(f"Level to {tgt} — behind for {stage}",
                         f"You're level {level} at {stage}; standard pacing is {tgt}. Buy XP to hold board "
                         f"strength and trait breakpoints — unless you're deliberately rolling here.", "warn")]
        if level > tgt:
            return [_rec(f"Ahead on level ({level} at {stage})",
                         f"Above the {tgt} curve for {stage} — you can roll harder or bank econ; just don't "
                         f"out-level your board.", "info")]
        return [_rec(f"On the level curve ({level} at {stage})",
                     f"Right on pace ({tgt}) for {stage}. Keep econ and hit your spikes.", "info")]

    def item_choice(self, offered, comp) -> list[dict]:
        """When you're offered items (armory/anvil), flag which belong on your carry.

        Matches each offered item/component against the carry's BIS items + the
        components that build them. Returns [{name, take, carry}] for the UI.
        """
        if not offered or not comp:
            return []

        def norm(x):
            return "".join(ch for ch in (x or "").lower() if ch.isalnum())

        want = set()
        for key in ("carry_items", "carry_components", "flexible_components"):
            for i in (comp.get(key) or []):
                want.add(norm(i))
                for part in cdragon.item_components(i):   # completed item -> its components
                    want.add(norm(part))
        carry = comp.get("carry") or "your carry"
        out = []
        for it in offered:
            ni = norm(it)
            take = bool(ni) and any(ni == w or (len(ni) >= 4 and (ni in w or w in ni)) for w in want)
            out.append({"name": it, "take": take, "carry": carry})
        return out

    def item_holder_advice(self, comp) -> list[dict]:
        """Who actually holds the items — and whether to slam now or hold for the carry.

        Cheap reroll carry (1-2 cost) -> it IS the holder, itemize it. A 3+ cost carry
        -> build the items but HOLD them; don't waste them on an early 1-cost you'll sell.
        """
        if not comp:
            return []
        carry = comp.get("carry")
        if not carry or carry.lower() == "flex":
            return []
        items = ", ".join(comp.get("carry_items") or []) or "your carry's items"
        playstyle = (comp.get("playstyle") or "").lower()
        cost = comp.get("carry_cost") or cdragon.cost_of(carry)
        reroll = playstyle == "reroll" or (cost is not None and cost <= 2)
        if reroll:
            return [_rec(f"Itemize {carry} — your carry",
                         f"{carry} is your reroll carry, so they hold the items. Slam {items} onto {carry} "
                         f"as you collect the pieces.", "buy")]
        cost_txt = f"a {cost}-cost" if cost else "a late-game unit"
        return [_rec(f"Hold items for {carry} — don't itemize a holder",
                     f"{carry} is your carry ({cost_txt}) and comes online late. Build toward {items}, but "
                     f"HOLD the items — don't slam them onto an early 1-cost you'll sell. Put them on {carry} "
                     f"when you hit it.", "warn")]

    # ---- formatting ----------------------------------------------------------
    def say(self, recs: list[dict]) -> str:
        out = []
        # Stable sort: time-boxed choices first, everything else keeps insertion order.
        for r in sorted(recs, key=lambda r: -r.get("priority", 0)):
            urgent = r.get("priority", 0) >= ACTIVE_CHOICE
            head = ""
            if urgent:
                head = "⏳ DECIDE NOW" + (f" (~{r['timer']}s)" if r.get("timer") else "") + " — "
            line = f"  {NAME}: {head}{r['text']}"
            if r.get("why"):
                line += f"\n      why: {r['why']}"
            if r.get("stat"):
                line += f"\n      stat: {r['stat']}"
            out.append(line)
        return "\n".join(out)

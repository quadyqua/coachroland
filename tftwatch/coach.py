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
                "You're not contesting each other — good. Build a comp that covers what they don't "
                "(different damage type / a frontline if they're squishy) so your team beats more "
                "matchups together.",
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
    def early_game(self, plan: dict, stage=None) -> list[dict]:
        """plan = {name, carry, early:[holders], level_plan} -> an IMPORTANT buy rec.

        Solves "I know my level-8 comp but not what to play before it." The holder
        list comes from comp-guide data (a meta source). Suppressed from stage 4 on:
        by then you're on your real board, so early-bridge advice is stale.
        """
        act = None
        if stage:
            try:
                act = int(str(stage).split("-")[0])
            except Exception:
                act = None
        if act is not None and act >= 4:
            return []
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

    # trait-name keywords -> the COUNTER_DYNAMICS archetype they imply. Set-agnostic on
    # purpose (matches by substring), so it survives set rotations without a hard-coded
    # per-set table. A comp can trip more than one; we counter the strongest.
    _TRAIT_ARCHETYPE = {
        "heavy_frontline": ("bastion", "bruiser", "juggernaut", "sentinel", "guardian",
                            "warden", "vanguard", "titan", "brawler", "colossus", "knight"),
        "assassins": ("assassin", "duelist", "slayer", "ambusher", "reaper", "shadow",
                      "rogue", "galaxy hunter"),
        "backline_carry": ("sniper", "gunner", "arcanist", "sorcerer", "mage", "marksman",
                           "invoker", "deadeye", "hunter", "dragon"),
    }

    def _archetypes(self, traits):
        """Active trait profile -> ordered list of (archetype, [trait names]) it implies,
        strongest (highest total unit count) first."""
        hits = {}
        for t in (traits or []):
            nm, cnt = (t or {}).get("name"), (t or {}).get("count") or 0
            if not nm or cnt < 2:                       # a 1-of a trait isn't a comp identity
                continue
            nl = nm.lower()
            for arch, keys in self._TRAIT_ARCHETYPE.items():
                if any(k in nl for k in keys):
                    a = hits.setdefault(arch, {"count": 0, "traits": []})
                    a["count"] += cnt
                    a["traits"].append(nm)
        return sorted(((arch, v["traits"], v["count"]) for arch, v in hits.items()),
                      key=lambda x: -x[2])

    def counter_comp(self, name, traits=None, carry=None, is_next=False) -> list[dict]:
        """Concrete counter advice for a scouted opponent, from their trait profile (+carry
        if known). Names the threat, then how to beat it: positional/item counter for their
        strongest archetype, and a tempo read from the carry's cost (punish-early vs respect
        their scaling). Qualitative only — no win-rates (Riot TFT policy).
        """
        traits = traits or []
        archs = self._archetypes(traits)
        if not archs and not carry:
            return []
        who = name or "your next opponent"
        sev = "warn" if is_next else "info"
        # headline: who + their identity (top archetype's traits, or the carry)
        top_traits = archs[0][1] if archs else []
        ident = ", ".join(top_traits) if top_traits else (carry or "their board")
        lead = f"You fight {who} next" if is_next else f"{who}'s comp scouted"
        out = [_rec(f"{lead}: {ident}",
                    f"You have a read on {who} — build the fight around it instead of guessing. "
                    f"Details below.", sev)]
        # the strongest archetype's counter (reuse the curated dynamics)
        if archs:
            arch = archs[0][0]
            tip = compguide.COUNTER_DYNAMICS.get(arch)
            if tip:
                out.append(_rec(f"Counter {who}: {arch.replace('_', ' ')}", tip, sev))
        # tempo read from their carry cost
        if carry:
            cost = cdragon.cost_of(carry)
            if cost and cost <= 2:
                out.append(_rec(f"{who} is a reroll board ({carry})",
                                f"{carry} is a {cost}-cost reroll — {who} is strongest NOW and fades late. "
                                f"Don't trade evenly into them; stay healthy and out-scale with your late game.",
                                sev))
            elif cost and cost >= 4:
                out.append(_rec(f"{who} scales on {carry} ({cost}-cost)",
                                f"{carry} is a {cost}-cost that comes online late — {who} is beatable BEFORE they "
                                f"hit it. Keep board strength up now so they bleed before their spike.", sev))
        return out

    # ---- in-game choices: Gods (2 offered) + augments (3 offered) -------------
    def choose_god(self, offered: list[str], playstyle: str = "flex") -> list[dict]:
        """Pick the better of the 2 offered Gods. Priority for a beginner: a God that FITS
        your playstyle > lower variance (reliable) > our patch preference order."""
        if not offered:
            return []
        pref = _GOD_PREF.get(playstyle, _GOD_PREF["flex"])
        var_rank = {"low": 0, "mid": 1, "high": 2}

        def score(g):
            info = compguide.GODS.get(g, {})
            best = (info.get("best_for") or "").lower()
            fits = best in ("any", playstyle) or playstyle in best or best in playstyle
            return (0 if fits else 1,
                    var_rank.get(info.get("variance"), 1),
                    pref.index(g) if g in pref else 99)

        pick = sorted(offered, key=score)[0]
        info = compguide.GODS.get(pick, {})
        other = next((g for g in offered if g != pick), None)
        why = (f"{pick} gives {info.get('gives', 'value')} — {info.get('note', '')} "
               f"({info.get('variance', '?')}-variance).")
        if other:
            why += f" Better than {other} for your {playstyle} line."
        return [_rec(f"God: take {pick}", why, "buy", priority=ACTIVE_CHOICE, timer=30)]

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
            if stage and str(stage)[:1] in ("4", "5", "6") and any(k in al for k in
                    ("combat", "damage", "crit", "heal", "health", "armor", "shield")):
                s += 1                                   # combat augments pay off more late
            return s

        pick = sorted(offered, key=score, reverse=True)[0]
        return [_rec(
            f"Augment: take {pick}",
            "Best of the three for your board. Rule of thumb: an emblem that points your comp > a "
            "proven strong augment > econ early / combat later. (Live win-rates/placements are "
            "intentionally not shown — Riot's TFT policy prohibits it; save stat review for post-game.)",
            "buy", stat=None,
            priority=ACTIVE_CHOICE, timer=30)]

    def shop_plan(self, shop, comp, gold=None, partner_comp=None, partner_name=None,
                  owned=None, contested=None) -> list[dict]:
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
        contested_set = {c.lower() for c in (contested or [])}   # opponent carries the lobby is heavy on

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
            deny = bool(name) and not mine and not pair and not theirs and nl in contested_set
            action, who = None, None
            if mine or pair:
                action, who = ("buy" if affordable else "lock"), "you"
            elif theirs:
                action, who = ("give" if affordable else None), "partner"
            elif deny:
                # A heavily-contested OPPONENT unit sitting in YOUR shop. Buying it (and
                # benching it) starves the teams chasing it — the safe, public-info version
                # of "sniping": no hidden copy-counts, just lobby contest.
                action, who = ("deny" if affordable else None), "deny"
            # WHY this unit: your carry / a comp trait-piece or body / a pair / your
            # partner's / a deny target the lobby is contesting.
            if is_my_carry:
                role = "carry"
            elif mine:
                utraits = {t.lower() for t in cdragon.champ_traits(name)}
                role = "core" if comp_primary and comp_primary in utraits else "body"
            elif pair:
                role = "pair"
            elif theirs:
                role = "partner"
            elif deny:
                role = "deny"
            else:
                role = None
            view.append({"name": name, "cost": cost, "action": action, "carry": is_my_carry,
                         "pair": pair, "tostar": tostar, "for": who, "role": role,
                         "partner": partner_name if theirs else None})

        # Gold-budget sequencing: with limited gold, keep the highest-priority buys you can
        # actually afford in order; downgrade the rest to lock (yours) / skip (partner's).
        if gold is not None:
            def _prio(v):
                if v["carry"]: return 0
                if v["pair"]: return 1
                if v["for"] == "you": return 2
                if v["for"] == "partner": return 3
                return 4   # deny — opportunistic, only with gold left after your own needs
            remaining = gold
            for v in sorted((x for x in view if x["action"] in ("buy", "give", "deny")),
                            key=lambda x: (_prio(x), x["cost"] if x["cost"] is not None else 99)):
                c = v["cost"]
                if c is not None and c <= remaining:
                    remaining -= c
                else:
                    v["action"] = "lock" if v["for"] == "you" else None
        return view

    def reroll_advice(self, gold, level, playstyle, stage=None, hp=None, carry=None) -> list[dict]:
        """When to reroll vs level vs save — from gold + level + playstyle, tuned by stage.

        HP overrides everything: if you're about to die, interest is worthless — roll it
        down NOW to stabilize. This beats "build to 50 gold" when you're sitting at 2 HP.
        """
        if gold is None:
            return []
        # Desperation / stabilize: low HP means you may not live to spend that gold.
        if hp is not None and hp <= 30:
            if gold >= 10:
                critical = hp <= 15
                return [_rec(("Roll it ALL down — you're at %d HP" % hp) if critical
                             else ("Roll down to stabilize — %d HP" % hp),
                             f"{hp} HP with {gold} gold — interest won't save you if you die. Spend it: roll "
                             f"to hit upgrades / 2-star your board and win the next fight. You can't take gold "
                             f"to the grave.", "danger" if critical else "warn")]
            return [_rec("Low HP (%d) — play your strongest board" % hp,
                         f"Only {gold} gold, so you can't roll much. Field your strongest units, position "
                         f"carefully, and scrap for the win this round.", "warn")]
        # Shop-odds-aware roll timing: when we know your carry's cost, the right level to roll
        # and whether you're leveling past its odds is pure math — so use it instead of the
        # generic advice below. (Odds vary slightly per set; the level thresholds are stable.)
        cost = cdragon.cost_of(carry) if carry else None
        if cost and level:
            target = compguide.roll_level_for(cost)
            o_now, o_tgt = compguide.odds(level, cost), compguide.odds(target, cost)
            if level < target:
                return [_rec(f"Level to {target} before you roll",
                             f"{carry} is a {cost}-cost — at level {level} it's only ~{o_now}% per shop slot vs "
                             f"~{o_tgt}% at level {target}. Buy XP to {target} first; rolling now mostly misses.",
                             "buy")]
            if cost <= 3 and level > target:
                return [_rec(f"Stop leveling — {carry} odds are dropping",
                             f"{carry} ({cost}-cost) peaks around level {target} (~{o_tgt}% per slot); at level "
                             f"{level} it's only ~{o_now}%. Roll here to hit it — don't level further.", "warn")]
            if gold >= 50:
                return [_rec(f"Roll now — you're at level {level} for {carry}",
                             f"You're at the level to hit your {cost}-cost {carry} (~{o_now}% per slot) with "
                             f"{gold} gold. Roll down to your floor to find copies; don't sit on gold past your spike.",
                             "buy")]
            return [_rec(f"Build to ~50 gold, then roll here for {carry}",
                         f"You're at the right level ({level}) for a {cost}-cost carry — get to ~50 gold, then roll "
                         f"down. Don't level past this.", "info")]
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

    def trouble(self, carry, rivals, alt="an open line") -> list[dict]:
        """'Am I in trouble?' — the CONTEST diagnosis. rivals = players seen on YOUR carry.
        Exactly one rival = a soft warn (you're splitting copies); 2+ is already handled by
        discourage/recommend, so this stays quiet there to avoid double-warning. We can't
        see a griefer benching your pieces (hidden info) — but the symptom (you stop hitting)
        and the fix (be pivot-ready) are the same, so the advice says so honestly.
        """
        rivals = [r for r in (rivals or []) if r]
        if not carry or len(rivals) != 1:
            return []
        return [_rec(
            f"{rivals[0]} is also on {carry}",
            f"One rival is splitting your {carry} copies. Not fatal — keep rolling — but watch your hits: "
            f"if the pool dries up (contested, or someone's holding your pieces), you'll both bottom out. "
            f"Stay ready to pivot to {alt}, or concede {carry} to them.", "warn")]

    def scout_prompt(self, players, known=None, next_opponent=None, stale=None) -> list[dict]:
        """Nudge you to scout an opponent you have NO read on (or a STALE read that predates
        5-costs) — prioritizing who you fight next. You do the scouting (click their
        portrait); we just flag who's worth a look. Self-resolves once seen.
        """
        players = players or []
        known = {k.lower() for k in (known or [])}
        stale = {s.lower() for s in (stale or [])}

        def unknown(p):
            n = p.get("name")
            return (bool(n) and not p.get("is_self") and not p.get("is_partner")
                    and n.lower() not in known and not p.get("unit"))

        if next_opponent:                              # you fight them THIS round -> highest value
            for p in players:
                if p.get("name") == next_opponent and unknown(p):
                    return [_rec(f"Scout {next_opponent} now — you fight them next",
                                 f"No read on {next_opponent}'s comp and they're your next opponent. Click their "
                                 f"portrait to see their board — knowing their carry lets Coach counter-position "
                                 f"you and flag if they contest your line.", "warn")]
        unk = [p for p in players if unknown(p)]
        if unk:                                        # otherwise the biggest blind spot
            top = max(unk, key=lambda p: p.get("hp") or 0)
            return [_rec(f"Scout {top['name']} when you get a chance",
                         f"No read on {top['name']} yet ({top.get('hp', '?')} HP). Peek at their board between "
                         f"rounds so their comp feeds into contest + counter advice.", "info")]
        # Everyone we can see is 'known', but a read taken before 5-costs is unreliable — a
        # 1-star legendary carry never shows on the star-up feed. Nudge a re-scout.
        re_stale = [p for p in players if p.get("name") and not p.get("is_self")
                    and p["name"].lower() in stale]
        if re_stale:
            top = max(re_stale, key=lambda p: p.get("hp") or 0)
            return [_rec(f"Re-scout {top['name']} — their read is stale",
                         f"You last saw {top['name']}'s comp before 5-costs came in. A 1-star legendary carry "
                         f"never shows on the star-up feed, so peek at their board again — they may have slotted "
                         f"a hidden carry.", "info")]
        return []

    def hard_switch(self, carry, contested, level, avoid=None) -> list[dict]:
        """The escape hatch. When YOUR carry is contested (starving you), find the best OPEN
        line whose carry you can actually HIT at your current level — combining contest
        (open_comps) with shop odds — and suggest a hard pivot. Quiet if your line isn't
        contested, or if nothing open is realistically hittable. `avoid` excludes lines you
        must not switch into (e.g. your Double Up partner's carry — never contest them).
        """
        if not carry or not level:
            return []
        if carry.lower() not in {c.lower() for c in (contested or [])}:
            return []                               # your line isn't contested -> don't suggest switching
        avoid_set = {carry.lower()} | {a.lower() for a in (avoid or []) if a}
        for c in compguide.open_comps(contested):   # tier-sorted -> first hittable line is the best
            oc = c.get("carry")
            if not oc or oc.lower() in avoid_set:
                continue
            cost = cdragon.cost_of(oc)
            if not cost:
                continue
            o = compguide.odds(level, cost)
            hittable = level >= compguide.roll_level_for(cost) or cost <= 2   # at roll level, or a rerollable low-cost
            if hittable and o > 0:
                return [_rec(
                    f"Hard-switch to {c['name']} — you can hit it now",
                    f"{carry} is contested and starving you, but {c['name']} is WIDE OPEN (nobody's on {oc}). "
                    f"Its {cost}-cost {oc} shows ~{o}% per shop slot at your level {level}, so you'll 2-star it "
                    f"fast where you're currently stuck. Pivot before you bleed out.", "buy")]
        return []

    def pool_check(self, carry, n_rivals) -> list[dict]:
        """Pool-size-aware contest read. A 5-cost pool is only 9, so even a 2-star is a
        scramble once contested; a 1-cost pool (30) tolerates it. Estimated from OBSERVED
        contesters (public) — we can't count hidden benches, so it's a pressure ESTIMATE,
        not an exact 'copies left'. Self-scales: small pools trip at 1 rival, big pools need
        many.
        """
        if not carry or not n_rivals:
            return []
        cost = cdragon.cost_of(carry)
        pool = compguide.POOL_SIZE.get(cost) if cost else None
        if not pool:
            return []
        est_left = max(pool - n_rivals * 4, 0)         # rough: each rival ties up ~4 copies
        if cost <= 3:                                  # reroll targets aim for a 3-star (9 copies)
            if est_left < 12:                          # not enough headroom to reliably 3-star
                return [_rec(f"3-star {carry} is slipping — the pool's thin",
                             f"{carry} is a {cost}-cost ({pool}-copy pool); with {n_rivals} other(s) on it only "
                             f"~{est_left} are likely left, so a 3-star (needs 9) is a long shot. Lock a 2-star "
                             f"and cap your board elsewhere, or hard-switch.", "warn")]
        elif n_rivals >= 1:                            # 4/5-cost: tiny pool, you're 2-starring
            return [_rec(f"{carry}'s pool is tiny and contested",
                         f"{carry} is a {cost}-cost — only {pool} exist and {n_rivals} other(s) want it. Even a "
                         f"2-star is a scramble: grab every copy the moment you see it, or pivot to an open carry.",
                         "warn")]
        return []

    def stabilize(self, hp, level, stage, gold=None, carry=None, early=None) -> list[dict]:
        """Concrete 'how to stop the bleeding' when you're low — the real, ordered levers a
        losing player can pull, NOT a useless 'stabilize or concede'. Fires when you're
        actually bleeding (<=40 HP)."""
        if hp is None or hp > 40:
            return []
        try:
            act = int(str(stage).split("-")[0]) if stage else None
        except Exception:
            act = None
        pace = {2: 5, 3: 6, 4: 7, 5: 8, 6: 9, 7: 9}.get(act)   # rough level you should be at

        steps = []
        if carry:                                              # free wins first: items + board + position
            steps.append(f"slam your item components onto {carry} now — a slammed item that wins THIS fight "
                         f"beats holding for the perfect build")
        board = ", ".join((early or [])[:5])
        steps.append(f"field your STRONGEST board{f' ({board})' if board else ''}, tank in front and "
                     f"{carry or 'your carry'} in a back corner — a lot of losses are just bad positioning")
        if level and pace and level < pace:                   # board size when short-handed
            steps.append(f"buy XP toward level {pace} — you're short-handed, and a bigger, higher-tier board "
                         f"is the fastest way to start winning fights again")
        if gold and gold >= 20:                               # then spend gold to upgrade
            steps.append(f"roll your {gold}g to 2-star your units — don't hoard interest while you're dying")

        body = "Stop the bleeding, in order: " + "; ".join(f"({i + 1}) {s}" for i, s in enumerate(steps)) + "."
        return [_rec(f"You're bleeding at {hp} HP — here's how to actually stabilize", body, "danger")]

    def comp_progress(self, comp, owned, traits=None) -> list[dict]:
        """Shopping list: which of your comp's core units you have vs still need.

        'have' comes from shop-diff inference (flaky) refined by your TRAIT counts: if a
        trait is active at >= the number of your comp's units that carry it, you clearly
        field all of them — so we can mark those board units as had even if the shop-diff
        tracker missed the buy (board-from-traits inference)."""
        if not comp:
            return []
        board = comp.get("board") or comp.get("final_board") or comp.get("early_units") or []
        if not board:
            return []
        have = {o.lower() for o in (owned or [])}
        if traits:
            active = {(t.get("name") or "").lower(): (t.get("count") or 0) for t in traits}
            board_trait = {u: {x.lower() for x in cdragon.champ_traits(u)} for u in board}
            for u in board:
                if u.lower() in have:
                    continue
                for tr in board_trait[u]:
                    if tr in active:
                        n_with = sum(1 for b in board if tr in board_trait[b])
                        if active[tr] >= n_with:          # you field every comp-unit of this trait
                            have.add(u.lower())
                            break
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
        components that build them, so a RADIANT version of a BIS item (a strict upgrade)
        is caught too and marked `radiant`. Returns [{name, take, carry, radiant}].
        NOTE: Artifact-Anvil items (Titanic Hydra, Void Gauntlet, …) are a separate pool
        this doesn't yet advise on — see BUGS.md.
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
            radiant = take and "radiant" in (it or "").lower()   # radiant of a BIS = strict upgrade
            out.append({"name": it, "take": take, "carry": carry, "radiant": radiant})
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

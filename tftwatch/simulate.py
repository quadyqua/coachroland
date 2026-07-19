"""Scenario simulator — ask Coach Roland "what would you do?" for any board + shop, with
NO live game, screen capture, or API. Great for sanity-checking the coaching and for
learning what Roland recommends in a given spot.

    python -m tftwatch.simulate --board "Caitlyn,Briar,Rek'Sai" \
                                --shop "Meeple,Teemo,Caitlyn,Rek'Sai,Briar" --gold 20

    # pin a comp / stage / level, or mark lobby-contested carries:
    python -m tftwatch.simulate --board "Jinx,Rek'Sai" --shop "Jinx,Vex,Akali,Leona,Jhin" \
                                --comp primordian_jinx --stage 4-2 --level 8 --gold 44 \
                                --contested "Vex,Jhin"
"""
import argparse
import sys
from collections import Counter

from . import cdragon, compguide
from .coach import CoachRoland
from .ledger import Ledger
from .tracker import HitTracker
from .coaching import _comp_dicts, _rules_advice   # capture-free: no mss/watcher import


def _traits_of(units):
    """Active trait profile (name+count) for a list of units — same shape the readers emit."""
    tc = Counter()
    for u in units:
        for t in cdragon.champ_traits(u):
            tc[t] += 1
    return [{"name": t, "count": n} for t, n in sorted(tc.items(), key=lambda x: -x[1])]


def simulate(board, shop_names, gold=None, level=None, stage=None,
             comp_key=None, contested=None, partner_comp_key=None, partner_name="Partner",
             hp=None, rivals=None, next_opponent=None, opp_board=None, opp_carry=None,
             rolls=None, carry_seen=None):
    """Return Roland's read for a hypothetical spot (same logic the live watcher runs).
    Pass partner_comp_key to simulate DOUBLE UP (partner-aware shop + coaching). Pass
    next_opponent + opp_board (their units) to simulate having SCOUTED them -> counter advice."""
    owned = [b.strip() for b in board if b.strip()]
    contested = [c.strip() for c in (contested or []) if c.strip()]
    rivals = [r.strip() for r in (rivals or []) if r.strip()]
    opp_board = [b.strip() for b in (opp_board or []) if b.strip()]
    shop = [{"name": n.strip(), "cost": cdragon.cost_of(n.strip())} for n in shop_names if n.strip()]

    # active traits from your board (real trait names + counts)
    traits = _traits_of(owned)

    # comp: pinned, else the one your board points at (what the live coach auto-commits to)
    if comp_key:
        comp = compguide.comp_detail(comp_key)
    else:
        comp = compguide.suggest_for_traits(traits, contested, current_key=None) or None
    my_comp, my_plan = _comp_dicts(
        compguide.find(comp.get("key") or comp.get("carry")) if comp else None)

    # Double Up partner (optional): partner comp detail for shop 'give' flags, and a light
    # teammate_comp dict for the partner-aware coaching (contest-your-own-partner, cannon).
    partner_detail = compguide.comp_detail(partner_comp_key) if partner_comp_key else None
    teammate_comp = None
    if partner_comp_key:
        pcarry = (compguide.find(partner_comp_key) or {}).get("carry")
        teammate_comp = {"name": partner_name,
                         "carries": [pcarry] if pcarry and pcarry.lower() != "flex" else []}

    # 2+ rivals on your carry -> also mark it contested so the multi-contest danger fires
    # (mirrors the live watcher, where contested_carries and players_on both trip).
    if len(rivals) >= 2 and comp and comp.get("carry") and comp["carry"] not in contested:
        contested = contested + [comp["carry"]]

    # scouted opponent (optional): stash their comp in a ledger so counter advice fires,
    # exactly as the live watcher would once a scout populates it.
    ledger = Ledger()
    players = []
    if next_opponent:
        opp_traits = _traits_of(opp_board)
        if opp_traits:
            ledger.note_comp(next_opponent, opp_traits, stage=stage)
        if opp_carry:
            ledger.note_carry(next_opponent, opp_carry, stage=stage)
        players = [{"name": next_opponent, "hp": 100}]

    # "you're not hitting": simulate having rolled `rolls` times and seen `carry_seen` copies
    # of your carry, then let the tracker judge it against the shop odds.
    hit_report = None
    if rolls is not None and comp and comp.get("carry"):
        ht = HitTracker()
        ht.slots_seen = int(rolls) * 5
        ht.seen[comp["carry"]] = int(carry_seen or 0)
        hit_report = ht.report(comp["carry"], level)

    coach = CoachRoland()
    shop_view = coach.shop_plan(shop, comp, gold=gold, owned=owned, contested=contested,
                                partner_comp=partner_detail, partner_name=partner_name)
    econ = (coach.reroll_advice(gold, level, (comp or {}).get("playstyle"), stage=stage, hp=hp,
                                carry=(comp or {}).get("carry"))
            if gold is not None else [])
    advice = _rules_advice(coach, my_comp, my_plan, teammate_comp,
                           {"players": players, "next_opponent": next_opponent},
                           contested, [], "an open line",
                           stage=stage, level=level, traits=traits, rivals=rivals,
                           hp=hp, gold=gold, ledger=ledger, hit_report=hit_report)
    unresolved = [n["name"] for n in shop if n["cost"] is None]
    return {"owned": owned, "traits": traits, "comp": comp, "shop": shop_view,
            "econ": econ, "advice": advice, "unresolved": unresolved,
            "stage": stage, "level": level, "gold": gold, "hp": hp,
            "partner": (partner_detail["name"] if partner_detail else None)}


def _fmt(res) -> str:
    out = []
    meta = " · ".join(x for x in [
        f"stage {res['stage']}" if res["stage"] else None,
        f"lvl {res['level']}" if res["level"] is not None else None,
        f"{res['gold']}g" if res["gold"] is not None else None,
        f"{res['hp']} HP" if res.get("hp") is not None else None] if x)
    out.append(f"Board: {', '.join(res['owned']) or '(empty)'}" + (f"   |   {meta}" if meta else ""))
    out.append("Active traits: " + (", ".join(f"{t['name']} {t['count']}" for t in res["traits"]) or "none"))
    c = res["comp"]
    building = (f"{c['name']} (carry {c.get('carry')})" if c else "no comp yet")
    if res.get("partner"):
        building += f"   |   Double Up partner: {res['partner']}"
    out.append("Building: " + building)
    out.append("\nShop:")
    for s in res["shop"]:
        act = (s["action"] or "skip").upper()
        why = ((s.get("tostar") or {"carry": "your carry", "core": "comp core",
                                    "body": "frontline body", "deny": "contested — deny",
                                    "partner": "for partner"}.get(s.get("role"), ""))
               if s["action"] else "")   # no reason tag on a skipped (dim) slot
        cost = f"{s['cost']}g" if s["cost"] is not None else "?"
        out.append(f"  {s['name']:10} {cost:4} {act:5} {('· ' + why) if why else ''}")
    if res["econ"]:
        out.append("\nEcon: " + res["econ"][0]["text"])
    out.append("\nCoach says:")
    for r in res["advice"][:8]:
        out.append(f"  - {r['text']}")
    if res["unresolved"]:
        out.append("\n(unrecognized names — not current-set champions: "
                   + ", ".join(res["unresolved"]) + ")")
    return "\n".join(out).replace("★", "*")


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser(prog="tftwatch.simulate",
                                description="Ask Coach Roland what to do for a hypothetical board + shop.")
    p.add_argument("--board", default="", help="comma-separated units on your board/bench")
    p.add_argument("--shop", required=True, help="comma-separated shop units (the 5 cards)")
    p.add_argument("--gold", type=int, default=None)
    p.add_argument("--level", type=int, default=None)
    p.add_argument("--stage", default=None, help="e.g. 4-2")
    p.add_argument("--comp", default=None, help="pin a comp (compguide key or carry); else auto-suggested")
    p.add_argument("--contested", default="", help="comma-separated lobby-contested carries (for deny flags)")
    p.add_argument("--partner-comp", default=None, help="DOUBLE UP: partner's comp (key or carry)")
    p.add_argument("--partner", default="Partner", help="Double Up partner's name")
    p.add_argument("--hp", type=int, default=None, help="your current HP (drives 'roll to stabilize')")
    p.add_argument("--rivals", default="", help="names of players seen on YOUR carry (contest diagnosis)")
    p.add_argument("--next-opponent", default=None, help="name of who you fight next (for counter advice)")
    p.add_argument("--opp-board", default="", help="units you SCOUTED on the next opponent's board")
    p.add_argument("--opp-carry", default=None, help="the next opponent's carry, if you spotted it")
    p.add_argument("--rolls", type=int, default=None, help="'not hitting' check: how many times you've rolled")
    p.add_argument("--carry-seen", type=int, default=None, help="how many copies of your carry you've seen in those rolls")
    a = p.parse_args()
    res = simulate(a.board.split(","), a.shop.split(","), gold=a.gold, level=a.level,
                   stage=a.stage, comp_key=a.comp, contested=a.contested.split(","),
                   partner_comp_key=a.partner_comp, partner_name=a.partner, hp=a.hp,
                   rivals=a.rivals.split(","), next_opponent=a.next_opponent,
                   opp_board=a.opp_board.split(","), opp_carry=a.opp_carry,
                   rolls=a.rolls, carry_seen=a.carry_seen)
    print("\nCoach Roland — scenario\n" + "=" * 40)
    print(_fmt(res))


if __name__ == "__main__":
    main()

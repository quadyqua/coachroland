"""Post-game review — compliant by construction.

Pulls your own last TFT match from the Riot API (read-only, sanctioned) and breaks
it down for learning: placement, your comp + carry + items, augments, traits, and how
it lined up with the comp guide. Stat-heavy review belongs HERE, not in live play
(Riot's TFT policy prohibits live win-rates/placements — post-game is fine).

    python -m tftwatch.review "Name#TAG"            # your last game
    python -m tftwatch.review "Name#TAG" --platform euw1 --region europe

summarize_participant() is a pure function (a match participant -> a review dict) so
the analysis is unit-tested without any network.
"""
from . import cdragon, compguide


def _api_to_name(coll):
    return {c["api"]: c["name"] for c in coll if c.get("api")}


def summarize_participant(p: dict) -> dict:
    """A Riot TFT match participant -> structured review. Pure, no network."""
    item_names = _api_to_name(cdragon.current_set_items())
    aug_names = _api_to_name(cdragon.current_set_augments())

    units = []
    for u in (p.get("units") or []):
        api = u.get("character_id") or ""
        units.append({
            "name": cdragon.champ_name(api),
            "cost": cdragon.champ_cost(api),
            "star": u.get("tier"),
            "items": [item_names.get(i, cdragon.humanize(i)) for i in (u.get("itemNames") or [])],
        })
    # carry = the most-itemized unit, tie-broken by star then cost
    carry = max(units, key=lambda u: (len(u["items"]), u["star"] or 0, u["cost"] or 0)) if units else None

    traits = sorted(
        [{"name": cdragon.trait_name(t.get("name")), "units": t.get("num_units")}
         for t in (p.get("traits") or []) if (t.get("style") or 0) > 0],
        key=lambda t: -(t["units"] or 0))

    augments = [aug_names.get(a, cdragon.humanize(a)) for a in (p.get("augments") or [])]
    comp = compguide.comp_detail(carry["name"]) if carry else None

    return {
        "placement": p.get("placement"),
        "level": p.get("level"),
        "last_round": p.get("last_round"),
        "carry": carry,
        "units": units,
        "traits": traits,
        "augments": augments,
        "comp_match": comp.get("name") if comp else None,
        "comp_key": comp.get("key") if comp else None,
        "comp_bis": (comp.get("carry_items") if comp else None),
    }


def takeaways(s: dict) -> list[str]:
    """Plain-language learning points from a summary (qualitative — no win-rates)."""
    out = []
    place = s.get("placement")
    if place:
        verdict = "win" if place == 1 else ("top 4" if place <= 4 else "bottom 4")
        out.append(f"Placed {place} ({verdict}).")
    c = s.get("carry")
    if c:
        items = ", ".join(c["items"]) or "no items"
        out.append(f"Carry: {c['name']} {c.get('star') or '?'}★ with {items}.")
        bis = s.get("comp_bis")
        if s.get("comp_match"):
            out.append(f"Comp ≈ {s['comp_match']}.")
        if bis:
            ran = {i.lower() for i in c["items"]}
            missing = [b for b in bis if b.lower() not in ran]
            if missing:
                out.append(f"BIS for {c['name']} is {', '.join(bis)} — you were missing {', '.join(missing)}.")
            else:
                out.append(f"You had {c['name']}'s BIS items — nice.")
    if s.get("level") and s.get("last_round"):
        out.append(f"Reached level {s['level']} (out by {s['last_round']}).")
    if s.get("traits"):
        top = ", ".join(f"{t['name']} {t['units']}" for t in s["traits"][:4])
        out.append(f"Active traits: {top}.")
    if s.get("augments"):
        out.append(f"Augments: {', '.join(s['augments'])}.")
    return out


def review_last_game(riot_id: str, api_key: str, platform: str = "na1",
                     region: str = "americas") -> dict:
    """Fetch your most recent match and summarize it. Needs a Riot API key."""
    from .riot_client import RiotClient
    client = RiotClient(api_key, platform=platform, region=region)
    name, _, tag = riot_id.partition("#")
    puuid = client.account_by_riot_id(name.strip(), tag.strip())["puuid"]
    ids = client.match_ids(puuid, count=1)
    if not ids:
        return {"error": "no recent matches"}
    info = client.match(ids[0]).get("info", {})
    me = next((p for p in info.get("participants", []) if p.get("puuid") == puuid), None)
    if not me:
        return {"error": "you weren't found in that match"}
    s = summarize_participant(me)
    s["match_id"] = ids[0]
    s["takeaways"] = takeaways(s)
    return s


if __name__ == "__main__":
    import argparse
    import os
    from dotenv import load_dotenv
    load_dotenv()
    ap = argparse.ArgumentParser(prog="tftwatch.review", description="Post-game review of your last TFT match")
    ap.add_argument("riot_id", help="Your Riot ID, e.g. Name#TAG")
    ap.add_argument("--platform", default="na1")
    ap.add_argument("--region", default="americas")
    args = ap.parse_args()
    key = os.getenv("RIOT_API_KEY")
    if not key:
        raise SystemExit("Set RIOT_API_KEY in .env (free dev key at developer.riotgames.com).")
    r = review_last_game(args.riot_id, key, args.platform, args.region)
    if r.get("error"):
        raise SystemExit(r["error"])
    print(f"\n=== Last game review ({r['match_id']}) ===")
    for line in r["takeaways"]:
        print(f"  - {line}")

"""Extract a 'comp' from a match participant, then aggregate & predict.

A comp signature here = the player's strongest active traits (what defines the
board) plus their carry units (3-star or heavily itemized). We aggregate these
across a player's recent games to find what they spam, then predict their next
game with recency-weighted frequency.
"""
from dataclasses import dataclass, field

from .cdragon import champ_name, champ_cost, trait_name


@dataclass
class GameComp:
    placement: int
    level: int
    traits: list[str]          # human-readable, strongest first
    carries: list[str]         # human-readable carry units
    label: str                 # e.g. "Vanguard + Sniper"


@dataclass
class CompStat:
    label: str
    count: int = 0
    weighted: float = 0.0      # recency-weighted count
    placements: list[int] = field(default_factory=list)
    carries: set[str] = field(default_factory=set)

    @property
    def avg_placement(self) -> float:
        return sum(self.placements) / len(self.placements) if self.placements else 0.0


def extract_comp(participant: dict) -> GameComp:
    # Real comp-defining traits only: active, 2+ units, and not a per-champion
    # "unique" emblem trait (those just add noise). Sorted by investment.
    real = [
        t for t in participant.get("traits", [])
        if t.get("tier_current", 0) >= 1
        and t.get("num_units", 0) >= 2
        and "Unique" not in t.get("name", "")
    ]
    real.sort(key=lambda t: (t.get("num_units", 0), t.get("style", 0)), reverse=True)
    trait_names = [trait_name(t["name"]) for t in real[:3]]

    # Carries: 3-star units, or units holding 2+ completed items. The real carry
    # is the itemized, highest-cost unit -> rank by items then cost (so a 4-cost
    # damage unit beats a 3-star tank holding nothing).
    units = participant.get("units", [])

    def item_count(u):
        return len(u.get("itemNames") or u.get("items") or [])

    carries = [u for u in units if u.get("tier", 0) >= 3 or item_count(u) >= 2]
    carries.sort(
        key=lambda u: (item_count(u), champ_cost(u["character_id"]), u.get("tier", 0)),
        reverse=True,
    )
    carry_names = [champ_name(u["character_id"]) for u in carries[:3]]

    # Label the way players name comps: main carry + main trait ("Corki Astronaut").
    main_trait = trait_names[0] if trait_names else ""
    main_carry = carry_names[0] if carry_names else ""
    label = " ".join(x for x in (main_carry, main_trait) if x) or "Flex / Open"
    return GameComp(
        placement=participant.get("placement", 0),
        level=participant.get("level", 0),
        traits=trait_names,
        carries=carry_names,
        label=label,
    )


def aggregate(comps: list[GameComp]) -> list[CompStat]:
    """comps are newest-first. Returns comp stats sorted by recency-weighted use."""
    stats: dict[str, CompStat] = {}
    n = len(comps)
    for i, c in enumerate(comps):
        s = stats.setdefault(c.label, CompStat(label=c.label))
        s.count += 1
        s.weighted += (n - i) / n          # newest game weighted ~1.0, oldest ~1/n
        s.placements.append(c.placement)
        s.carries.update(c.carries)
    return sorted(stats.values(), key=lambda s: (s.weighted, -s.avg_placement), reverse=True)


def tendencies(comps: list[GameComp]):
    """Aggregate by trait and by carry across games -> (traits, carries).

    This catches what the full-comp label hides: e.g. a player whose comps all
    differ but who picks the same TRAIT every game (a real comfort signal).
    Each entry: {name, count, avg} sorted by frequency then placement.
    """
    def tally(getter):
        d: dict[str, dict] = {}
        for c in comps:
            for name in getter(c):
                e = d.setdefault(name, {"name": name, "count": 0, "places": []})
                e["count"] += 1
                e["places"].append(c.placement)
        for e in d.values():
            e["avg"] = sum(e["places"]) / len(e["places"]) if e["places"] else 0.0
        return sorted(d.values(), key=lambda e: (e["count"], -e["avg"]), reverse=True)

    return tally(lambda c: c.traits), tally(lambda c: c.carries)


def predict(stats: list[CompStat], total_games: int) -> dict:
    """Return the most likely comp for their next game + confidence + signal."""
    if not stats or total_games == 0:
        return {"comp": "Unknown", "confidence": 0.0, "signal": "no recent data"}

    top = stats[0]
    total_weight = sum(s.weighted for s in stats) or 1.0
    confidence = top.weighted / total_weight
    share = top.count / total_games

    if share >= 0.6:
        signal = "ONE-TRICK -- forces this almost every game"
    elif share >= 0.35:
        signal = "strong preference"
    elif len(stats) >= max(4, total_games * 0.7):
        signal = "flex player -- reads the lobby, hard to predict"
    else:
        signal = "leans this way"

    return {
        "comp": top.label,
        "confidence": confidence,
        "share": share,
        "avg_placement": top.avg_placement,
        "carries": sorted(top.carries)[:3],
        "signal": signal,
    }

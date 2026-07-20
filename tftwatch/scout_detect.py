"""Scout detection from the left trait panel — anchored to YOUR committed comp.

While you're on your own board the left panel shows YOUR active traits; when you click an
opponent to scout, it swaps to THEIRS. The tell: your comp's DEFINING trait (e.g. Space
Groove for a Space Groove line) is active on your board and absent on theirs.

v1 compared the panel to a rolling baseline of recent reads — but that baseline grew to
include every trait you'd ever fielded, so a common trait (Bastion/N.O.V.A.) an opponent
shared let their board pass as yours (real bug, live game 2026-07-19). v2 anchors to the
COMMITTED comp instead (stable, and rock-solid once you declare your line in the picker):

  it's a SCOUT when your comp's defining trait is NOT active in the panel, or the panel
  barely overlaps your comp's traits.

Fail-safe: with no committed comp, or too few traits to judge, we assume it's your own
board — a missed scout only leaks a trait read; a false scout could hide real advice.
"""


def comp_trait_names(comp) -> set:
    """Lowercase trait names a committed comp FIELDS — its declared traits AND every trait its
    board units carry. Rich on purpose: your board drifts (you flex a frontline, a trait falls
    off), so a one-trait anchor false-flags your own board. The full fielded set is stable."""
    from . import cdragon
    names = {(t or "").lower() for t in ((comp or {}).get("traits") or []) if t}
    for u in ((comp or {}).get("board") or []) + ((comp or {}).get("early_units") or []):
        for t in cdragon.champ_traits(u):
            if t:
                names.add(t.lower())
    return names


def primary_trait(comp):
    """The comp's DEFINING trait (traits[0]) — the anchor the panel must show on your board."""
    tr = (comp or {}).get("traits") or []
    return (tr[0] or "").lower() if tr else None


def live_trait_names(traits) -> set:
    """All lowercase trait names present in a live panel read ([{name,count}, ...])."""
    return {(t.get("name") or "").lower() for t in (traits or []) if t and t.get("name")}


def _active_names(traits, breakpoint: int = 2) -> set:
    """Trait names active at a breakpoint (count >= breakpoint) — a real, fielded trait."""
    return {(t.get("name") or "").lower() for t in (traits or [])
            if t and t.get("name") and (t.get("count") or 0) >= breakpoint}


class ScoutDetector:
    """classify(live_traits, comp) -> ('self'|'scout', overlap). Anchored to `comp` (the
    committed/declared line). reset() is a no-op now (no accumulated state) but kept for the
    watcher's per-game reset call."""

    def __init__(self, min_live: int = 3, scout_max_overlap: float = 0.34):
        self.min_live = min_live
        self.scout_max_overlap = scout_max_overlap

    def reset(self) -> None:
        pass

    def classify(self, live_traits, comp=None):
        anchor = comp_trait_names(comp)
        active = _active_names(live_traits)   # traits fielded at a breakpoint (count >= 2)
        # Fail-safe: need a committed comp to anchor on AND enough active traits to judge.
        # Otherwise assume it's your own board — a false scout would hide your real advice,
        # which is worse than missing one (a missed scout just skips that opponent's counter).
        if not anchor or len(active) < 3:
            return ("self", 1.0)
        # A SCOUT is a panel whose active traits barely overlap the traits YOUR comp fields.
        overlap = len(active & anchor) / len(active)
        if overlap <= self.scout_max_overlap:
            return ("scout", overlap)
        return ("self", overlap)

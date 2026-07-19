"""Scout detection from the left trait panel — no new region, no calibration frame.

Insight (validated across 36 real captured frames): while you're on YOUR OWN board the
left trait-panel read is rock-stable — the same comp every frame (Primordian/Anima/
Challenger/Rogue/Space Groove). It only changes to a DIFFERENT profile when you click an
opponent's portrait to scout them (the panel swaps to THEIR traits). So a live panel that
doesn't match your comp = a scout is active.

We judge "yours" from two sources, unioned: your committed comp's traits (derived from its
board), and a rolling baseline of your recent self-reads (which converges to your comp even
before one is committed). A frame whose traits barely overlap that set is a scout.

This is deliberately conservative: it fires only when MOST of the panel is foreign, so
your own board (and away-combat, where the panel is still yours) never trips it. Whose
board you're scouting ("who") is resolved separately by the caller.
"""
from collections import Counter

from . import cdragon


def comp_trait_names(comp) -> set:
    """Lowercase trait names implied by a committed comp's board (or early units)."""
    board = ((comp or {}).get("board") or (comp or {}).get("final_board")
             or (comp or {}).get("early_units") or [])
    names = set()
    for u in board:
        for t in cdragon.champ_traits(u):
            if t:
                names.add(t.lower())
    return names


def live_trait_names(traits) -> set:
    """Lowercase trait names from a live panel read ([{name,count}, ...])."""
    return {(t.get("name") or "").lower() for t in (traits or []) if t and t.get("name")}


class ScoutDetector:
    """Classifies each trait-panel read as 'self' or 'scout', maintaining a rolling
    baseline of what YOUR panel looks like. reset() between games.

    classify(live_traits, comp) -> ('self'|'scout', overlap_fraction). overlap = the
    fraction of the live panel that IS your traits; low overlap => scout.
    """

    def __init__(self, window: int = 15, self_min_frac: float = 0.4,
                 scout_max_overlap: float = 0.34, min_live: int = 3):
        self.window = window
        self.self_min_frac = self_min_frac
        self.scout_max_overlap = scout_max_overlap
        self.min_live = min_live
        self.reset()

    def reset(self) -> None:
        self._recent: list = []       # recent self-classified trait-name sets

    def _record(self, live: set) -> None:
        self._recent.append(frozenset(live))
        if len(self._recent) > self.window:
            self._recent.pop(0)

    def _baseline(self, comp) -> set:
        """Your trait names = committed-comp traits UNION the traits that show up in a
        healthy fraction of your recent self-reads."""
        names = comp_trait_names(comp)
        if self._recent:
            c = Counter()
            for s in self._recent:
                c.update(s)
            thresh = max(1, int(len(self._recent) * self.self_min_frac))
            names |= {n for n, k in c.items() if k >= thresh}
        return names

    def classify(self, live_traits, comp=None):
        live = live_trait_names(live_traits)
        base = self._baseline(comp)
        # too little to judge, or no baseline yet -> treat as your own & seed the baseline
        if len(live) < self.min_live or not base:
            if live:
                self._record(live)
            return ("self", 1.0)
        overlap = len(live & base) / len(live)
        if overlap <= self.scout_max_overlap:
            return ("scout", overlap)        # mostly-foreign panel -> a scout is active
        self._record(live)                   # matches you -> reinforce the baseline
        return ("self", overlap)

"""Per-game augment/commitment ledger.

We can only ever read what's on YOUR screen and what you choose to scout (no
automation, no hidden info). So a player's augments and carry fill in
*opportunistically*: yours continuously, your partner's and opponents' whenever you
view their board. The ledger remembers what's been seen for the rest of the game so
the brain reasons off accumulated knowledge instead of a single frame — and clearly
marks who's still UNKNOWN so it knows what's worth scouting.

Reset between games (nothing carries over). Structured data only, never images.
"""


def _act(stage):
    """The act (first) number of a stage string like '4-6' -> 4, else None."""
    try:
        return int(str(stage).split("-")[0])
    except Exception:
        return None


class Ledger:
    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.augments: dict[str, list[str]] = {}   # player name -> augments seen
        self.carries: dict[str, str] = {}          # player name -> their spiked carry
        self.carry_seen_at: dict[str, str] = {}    # player name -> stage the carry was last read

    def note_augments(self, name: str, augs) -> None:
        if not name or not augs:
            return
        cur = self.augments.setdefault(name, [])
        for a in augs:
            if a and a not in cur:
                cur.append(a)

    def note_carry(self, name: str, carry: str, stage: str = None) -> None:
        if name and carry:
            self.carries[name] = carry
            if stage:
                self.carry_seen_at[name] = stage

    def stale_reads(self, current_stage) -> list[str]:
        """Players whose carry read predates 5-costs (read at stage < 5 while it's now >= 5).
        Their read may be outdated — a 1-star 5-cost carry never shows on the star-up feed,
        so a re-scout is worth it. Empty until 5-costs matter (stage 5+)."""
        cur = _act(current_stage)
        if cur is None or cur < 5:
            return []
        return sorted(n for n, seen in self.carry_seen_at.items()
                      if (_act(seen) or 99) < 5)

    def augments_for(self, name: str) -> list[str]:
        return self.augments.get(name, [])

    def carry_for(self, name: str):
        return self.carries.get(name)

    def players_on(self, carry: str) -> list[str]:
        """Names of players observed on a given carry — contest visibility (public/scouted
        info only; we never see benches, so this is who's *shown* they're on it)."""
        if not carry:
            return []
        cl = carry.lower()
        return sorted(n for n, c in self.carries.items() if c and c.lower() == cl)

    def contested_carries(self, min_players: int = 2) -> list[str]:
        """Carries that >= min_players DISTINCT players are on, across everything seen this
        game (not just the current frame) — accumulates as opponents star up over time."""
        from collections import Counter
        counts = Counter(c for c in self.carries.values() if c)
        return sorted({c for c, n in counts.items() if n >= min_players})

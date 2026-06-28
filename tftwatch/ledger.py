"""Per-game augment/commitment ledger.

We can only ever read what's on YOUR screen and what you choose to scout (no
automation, no hidden info). So a player's augments and carry fill in
*opportunistically*: yours continuously, your partner's and opponents' whenever you
view their board. The ledger remembers what's been seen for the rest of the game so
the brain reasons off accumulated knowledge instead of a single frame — and clearly
marks who's still UNKNOWN so it knows what's worth scouting.

Reset between games (nothing carries over). Structured data only, never images.
"""


class Ledger:
    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.augments: dict[str, list[str]] = {}   # player name -> augments seen
        self.carries: dict[str, str] = {}          # player name -> their spiked carry

    def note_augments(self, name: str, augs) -> None:
        if not name or not augs:
            return
        cur = self.augments.setdefault(name, [])
        for a in augs:
            if a and a not in cur:
                cur.append(a)

    def note_carry(self, name: str, carry: str) -> None:
        if name and carry:
            self.carries[name] = carry

    def augments_for(self, name: str) -> list[str]:
        return self.augments.get(name, [])

    def carry_for(self, name: str):
        return self.carries.get(name)

    def contested_carries(self, min_players: int = 2) -> list[str]:
        """Carries that >= min_players DISTINCT players are on, across everything seen this
        game (not just the current frame) — accumulates as opponents star up over time."""
        from collections import Counter
        counts = Counter(c for c in self.carries.values() if c)
        return sorted({c for c, n in counts.items() if n >= min_players})

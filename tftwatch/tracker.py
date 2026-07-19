"""Infer what you've bought by watching the SHOP — no bench reading needed.

We read the shop reliably (champion names via OCR) but not the bench (icons). So we
infer purchases by diffing the shop between reads: when a unit leaves the shop while
the rest stays put (i.e. NOT a full reroll) and your gold drops, you bought it.
Accumulated, that approximates what you own -> powers pair detection without ever
recognizing a bench tile.

It's an APPROXIMATION. It counts BUYS, so it drifts on sells, 2-/3-star combines, and
units cannoned to/from a Double Up partner. Good for "you've bought 2 Caitlyns -> a
third makes a 2-star"; not a precise bench snapshot.
"""
from collections import Counter

from . import cdragon, compguide


class PurchaseTracker:
    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self._prev = None
        self._prev_gold = None
        self.bought = Counter()        # inferred units bought this game

    def update(self, shop_names, gold=None) -> None:
        """Feed the current shop (list of champion names) + gold; infer any purchase."""
        names = [n for n in (shop_names or []) if n]
        if self._prev is not None:
            prev, curr = Counter(self._prev), Counter(names)
            left = prev - curr                 # units that disappeared since last read
            total_left = sum(left.values())
            kept = sum((prev & curr).values())
            # A buy empties 1-2 slots while everything else stays; a reroll replaces ~all 5.
            looks_like_buy = 0 < total_left <= 2 and kept == len(self._prev) - total_left
            gold_dropped = (gold is not None and self._prev_gold is not None
                            and gold < self._prev_gold)
            # Require a gold drop when gold is readable; otherwise fall back to shape alone.
            if looks_like_buy and (gold is None or self._prev_gold is None or gold_dropped):
                self.bought.update(left)
        self._prev = names
        if gold is not None:
            self._prev_gold = gold

    def owned(self) -> list:
        """Inferred units you've bought this game (with multiplicity), for pair detection."""
        return list(self.bought.elements())


_distinct_at_cost: dict = {}


def _distinct_units_at_cost(cost):
    """How many DISTINCT champions exist at a cost tier this set (from the roster). Needed to
    turn the per-slot cost-tier odds into the odds of YOUR specific unit showing up."""
    if not _distinct_at_cost:
        for n in cdragon.current_roster():
            c = cdragon.cost_of(n)
            if c:
                _distinct_at_cost[c] = _distinct_at_cost.get(c, 0) + 1
    return _distinct_at_cost.get(cost)


class HitTracker:
    """'Are you actually hitting?' — counts copies of your carry SEEN in the shop vs how many
    the shop odds predict you should have seen by now. A big shortfall means the pool's dry:
    contested and drained, or someone's benching your copies to block you. We can't see benches
    (hidden info), but the SYMPTOM (you stop hitting) is public and the fix is the same.

    Fed the same shop stream as PurchaseTracker. Counts NEW slots between reads (so a buy that
    changes 1-2 slots and a full reroll both contribute correctly), and per-unit appearances.
    Estimate, not exact — it can't know the true copies left, only what your shop showed you.
    """

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self._prev = None
        self.slots_seen = 0            # total NEW shop slots observed this game
        self.seen = Counter()          # per-unit appearances across those new slots

    def update(self, shop_names) -> None:
        names = [n for n in (shop_names or []) if n]
        if self._prev is not None:
            added = Counter(names) - Counter(self._prev)   # units newly on offer since last read
            self.slots_seen += sum(added.values())
            self.seen.update(added)
        self._prev = names

    def report(self, carry, level, min_slots: int = 25, min_expected: float = 2.0,
               ratio: float = 0.4):
        """{hitting, carry, seen, expected, rolls, slots} or None. hitting: True=on pace,
        False=falling well short (warn), None=not enough data yet / not at roll level."""
        if not carry or not level:
            return None
        cost = cdragon.cost_of(carry)
        if not cost or level < compguide.roll_level_for(cost):
            return None                                    # not rolling for it yet -> don't judge
        distinct = _distinct_units_at_cost(cost)
        if not distinct:
            return None
        # chance a given slot is YOUR specific unit ~ P(slot is this cost tier) / distinct-at-cost
        p = (compguide.odds(level, cost) / 100.0) / distinct
        expected = self.slots_seen * p
        actual = self.seen.get(carry, 0)
        base = {"carry": carry, "seen": actual, "expected": round(expected, 1),
                "rolls": round(self.slots_seen / 5.0), "slots": self.slots_seen}
        if self.slots_seen < min_slots or expected < min_expected:
            return {**base, "hitting": None}               # too small a sample to call it
        return {**base, "hitting": actual > expected * ratio}

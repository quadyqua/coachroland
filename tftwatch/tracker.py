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

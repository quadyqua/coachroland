"""'You're not hitting' — copies-of-carry seen vs the odds -> pool-is-dry warning.

    python tests/test_hitting.py     (or: pytest tests/test_hitting.py)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tftwatch import cdragon                       # noqa: E402
from tftwatch.tracker import HitTracker            # noqa: E402
from tftwatch.coach import CoachRoland             # noqa: E402
from tftwatch.simulate import simulate             # noqa: E402

C = CoachRoland()


def _carry(cost):
    return next((n for n in cdragon.current_roster() if cdragon.cost_of(n) == cost), None)


def test_update_counts_new_slots_not_kept_ones():
    ht = HitTracker()
    ht.update(["Jinx", "Vex", "Akali"])            # first read: no baseline yet, nothing counted
    assert ht.slots_seen == 0
    ht.update(["Jinx", "Leona", "Jhin"])           # Jinx kept; Leona+Jhin are new
    assert ht.slots_seen == 2 and ht.seen["Leona"] == 1 and ht.seen.get("Jinx", 0) == 0
    ht.update(["Jinx", "Jinx", "Jhin"])            # a second Jinx now on offer = one new sighting
    assert ht.seen["Jinx"] == 1


def test_report_none_until_enough_rolls_and_only_at_roll_level():
    carry = _carry(1) or "Jinx"
    ht = HitTracker()
    ht.slots_seen, ht.seen[carry] = 10, 0          # tiny sample
    assert ht.report(carry, level=8) is None or ht.report(carry, level=8)["hitting"] is None
    # below the carry's roll level -> we don't judge (you're not rolling for it yet)
    low = HitTracker(); low.slots_seen, low.seen[carry] = 200, 0
    assert low.report(carry, level=2) is None


def test_flags_not_hitting_when_far_below_expected():
    carry = _carry(1) or "Jinx"
    ht = HitTracker()
    ht.slots_seen, ht.seen[carry] = 300, 0         # slow-rolled hard (~60 rolls), seen ZERO
    rep = ht.report(carry, level=8)
    assert rep and rep["hitting"] is False and rep["expected"] >= 2
    recs = C.not_hitting(rep, alt="an open line")
    assert recs and "not hitting" in recs[0]["text"].lower()
    assert "lock" in recs[0]["why"].lower() and "pivot" in recs[0]["why"].lower()


def test_quiet_when_hitting_on_pace():
    carry = _carry(1) or "Jinx"
    ht = HitTracker()
    ht.slots_seen, ht.seen[carry] = 300, 100       # seen plenty
    rep = ht.report(carry, level=8)
    assert rep and rep["hitting"] is True
    assert C.not_hitting(rep) == []                # on pace -> silent


def test_simulate_exposes_not_hitting():
    board, shop = ["Jinx", "Rek'Sai"], ["Jinx", "Vex", "Akali", "Leona", "Jhin"]

    def has(res, sub):
        return any(sub.lower() in a["text"].lower() for a in res["advice"])

    dry = simulate(board, shop, comp_key="primordian_jinx", stage="4-2", level=8,
                   rolls=30, carry_seen=0)
    assert has(dry, "not hitting")
    fine = simulate(board, shop, comp_key="primordian_jinx", stage="4-2", level=8,
                    rolls=30, carry_seen=20)
    assert not has(fine, "not hitting")


if __name__ == "__main__":
    from tftwatch import cdragon
    cdragon.ensure_loaded()                # fail loudly on a cold cache, not a misleading 18/20
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)

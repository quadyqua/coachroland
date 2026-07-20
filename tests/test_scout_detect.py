"""Scout detection: a trait panel that doesn't match YOUR committed comp = a scout.

v2 anchors to the committed comp (stable), not a rolling baseline (which drifted and let
opponents' common traits pass as yours in a real game). Validated on two image-ground-truthed
frames from that game: the user's own Space Groove board -> self; a scout of CrownedOmega -> scout.

    python tests/test_scout_detect.py     (or: pytest tests/test_scout_detect.py)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tftwatch import compguide                       # noqa: E402
from tftwatch.scout_detect import ScoutDetector, comp_trait_names   # noqa: E402


def _p(*pairs):
    """Panel read shape: [{name,count}, ...] from (name, count) pairs."""
    return [{"name": n, "count": c} for n, c in pairs]


SPACE_GROOVE = compguide.comp_detail("space_groove")


def test_own_board_matching_comp_is_self():
    # active traits all belong to your comp's fielded set -> your own board
    own = _p(("Space Groove", 2), ("Bastion", 3), ("Rogue", 2), ("Timebreaker", 2))
    assert ScoutDetector().classify(own, SPACE_GROOVE)[0] == "self"


def test_foreign_board_is_a_scout():
    # a panel whose active traits are mostly NOT in your comp -> scouting someone
    foreign = _p(("Brawler", 4), ("Psionic", 2), ("N.O.V.A.", 2))   # CrownedOmega's real board
    assert ScoutDetector().classify(foreign, SPACE_GROOVE)[0] == "scout"
    conduit = _p(("Arbiter", 3), ("Conduit", 2), ("Voyager", 2))
    assert ScoutDetector().classify(conduit, SPACE_GROOVE)[0] == "scout"


def test_no_committed_comp_never_flags_a_scout():
    # nothing to anchor on -> assume own board (a false scout would hide your real advice)
    foreign = _p(("Brawler", 4), ("Psionic", 2), ("N.O.V.A.", 2))
    assert ScoutDetector().classify(foreign, None)[0] == "self"
    assert ScoutDetector().classify(foreign, {})[0] == "self"


def test_thin_read_is_not_judged():
    # fewer than 3 active traits (transition/combat/partial read) -> don't call it a scout
    assert ScoutDetector().classify(_p(("Bastion", 2), ("Rogue", 2)), SPACE_GROOVE)[0] == "self"
    assert ScoutDetector().classify([], SPACE_GROOVE)[0] == "self"


def test_anchor_is_rich_not_just_the_defining_trait():
    # the anchor must include board-derived traits, not only traits[0] — a one-trait anchor
    # false-flags your own board the moment a trait drops off.
    anchor = comp_trait_names(SPACE_GROOVE)
    assert "space groove" in anchor and len(anchor) >= 4


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

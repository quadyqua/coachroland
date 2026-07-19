"""Scout detection: a left-panel read that doesn't match YOUR comp = a scout is active.

    python tests/test_scout_detect.py     (or: pytest tests/test_scout_detect.py)
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tftwatch.scout_detect import ScoutDetector      # noqa: E402


def _p(*names):
    """Trait panel read shape: [{name,count}, ...]."""
    return [{"name": n, "count": 2} for n in names]


# The user's real, rock-stable own panel (observed across 36 captured frames).
SELF = _p("Primordian", "Anima", "Challenger", "Rogue", "Space Groove")
# A frontline opponent's panel (what a scout would swap the left bar to).
FRONTLINE = _p("Vanguard", "Bastion", "Brawler", "Marauder")


def test_own_panel_is_never_a_scout():
    d = ScoutDetector()
    for _ in range(20):                                 # your stable panel, frame after frame
        assert d.classify(SELF)[0] == "self"


def test_foreign_panel_trips_scout_after_baseline():
    d = ScoutDetector()
    for _ in range(5):                                  # establish your baseline first
        d.classify(SELF)
    tag, overlap = d.classify(FRONTLINE)
    assert tag == "scout" and overlap <= 0.34           # mostly-foreign -> scout
    # ...and it reverts the moment you're back on your own board (baseline unpolluted)
    assert d.classify(SELF)[0] == "self"


def test_committed_comp_seeds_the_baseline_before_any_history():
    # With a committed comp whose board yields your traits, a panel DISJOINT from those
    # traits is caught as a scout on the very first read (cold start, no self-history).
    from tftwatch import compguide
    from tftwatch.scout_detect import comp_trait_names
    comp = compguide.comp_detail("primordian_jinx")
    own = comp_trait_names(comp)
    assert own                                            # the comp yields some traits
    # a panel using traits your comp does NOT have (e.g. Fateweaver line) -> scout
    foreign = _p("Fateweaver", "Stargazer", "Conduit", "Voyager")
    assert not (own & {t["name"].lower() for t in foreign})   # genuinely disjoint
    d = ScoutDetector()
    assert d.classify(foreign, comp)[0] == "scout"


def test_too_few_traits_is_not_a_scout():
    d = ScoutDetector()
    for _ in range(5):
        d.classify(SELF)
    assert d.classify(_p("Bastion"))[0] == "self"        # 1-2 traits = transition, don't judge


def test_reset_clears_baseline():
    d = ScoutDetector()
    for _ in range(10):
        d.classify(SELF)
    d.reset()
    assert d._recent == []


def test_real_captured_frames_all_read_as_self():
    """Every one of the 36 real frames is the user's OWN board -> none should read as a
    scout. Skips cleanly if the (gitignored) capture set isn't present."""
    frames = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..",
                                           "fixtures", "live_capture", "frame*.png")))
    if not frames:
        print("  (skip: no live_capture frames on this machine)")
        return
    from PIL import Image
    from tftwatch import localvision as lv
    d = ScoutDetector()
    scouts = []
    for f in frames:
        tr = lv.read_traits_pil(Image.open(f).convert("RGB")).get("traits")
        if d.classify(tr)[0] == "scout":
            scouts.append(os.path.basename(f))
    assert not scouts, f"false scouts on own-board frames: {scouts}"


if __name__ == "__main__":
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

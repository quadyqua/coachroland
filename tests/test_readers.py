"""Vision regression tests — run the OCR readers against the committed REAL reference
frame and check them against the recorded expected output.

Slower than test_logic (loads RapidOCR), but this is what guards the screen-reading
side from silently breaking. No live game or network needed.

    python tests/test_readers.py     (or: pytest tests/test_readers.py)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tftwatch import localvision as lv          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAME = os.path.join(ROOT, "fixtures", "ref_1440p_planning.jpg")
GOD = os.path.join(ROOT, "fixtures", "god_choice.png")
EXP = json.load(open(os.path.join(ROOT, "fixtures", "ref_1440p_reads.json")))["expected_reads"]


def test_stage_matches_reference():
    assert lv.read_stage(FRAME)["stage"] == EXP["stage"]["stage"]


def test_shop_matches_reference():
    got = lv.read_self(FRAME)
    assert got["level"] == EXP["self"]["level"]
    assert [s["name"] for s in got["shop"]] == [s["name"] for s in EXP["self"]["shop"]]


def test_traits_match_reference():
    got = {t["name"] for t in lv.read_traits(FRAME)["traits"]}
    want = {t["name"] for t in EXP["traits"]["traits"]}
    assert got == want


def test_double_up_lobby_reads_all_eight():
    players = lv.read_lobby(FRAME)["players"]
    assert len(players) == 8                       # Double Up: all 8, not the old 4
    assert "QuadyQua" in [p["name"] for p in players]


def test_god_offer_reads_both():
    assert lv.read_offer(GOD)["options"] == ["Yasuo", "Aurelion Sol"]


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

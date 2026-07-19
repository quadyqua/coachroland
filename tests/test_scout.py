"""Scout prompt: nudge you to scout an opponent we have no read on (next opponent first).

    python tests/test_scout.py     (or: pytest tests/test_scout.py)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tftwatch.coach import CoachRoland          # noqa: E402

C = CoachRoland()
PLAYERS = [
    {"name": "TheJim", "hp": 80},                       # unknown, high HP
    {"name": "Me", "hp": 90, "is_self": True},          # you -> excluded
    {"name": "LooShiba", "hp": 50, "unit": "Jinx"},     # carry shown -> known
    {"name": "Dumbdummm", "hp": 30},                    # unknown, low HP
]


def _texts(recs):
    return " ".join(r["text"] for r in recs)


def test_prompts_next_opponent_first():
    recs = C.scout_prompt(PLAYERS, known=set(), next_opponent="TheJim")
    assert "Scout TheJim now" in _texts(recs)


def test_falls_back_to_biggest_unknown():
    # TheJim now read -> the remaining blind spot (Dumbdummm) is flagged
    recs = C.scout_prompt(PLAYERS, known={"TheJim"}, next_opponent=None)
    assert "Dumbdummm" in _texts(recs)


def test_quiet_when_everyone_is_known():
    assert C.scout_prompt([{"name": "A", "unit": "Jinx"}], known={"A"}) == []


def test_excludes_self_and_already_seen():
    joined = _texts(C.scout_prompt(PLAYERS, known=set()))
    assert "LooShiba" not in joined and "Me" not in joined   # seen carry + self are skipped


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

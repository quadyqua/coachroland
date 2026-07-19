"""The scenario simulator: Roland's call for a hypothetical board + shop, no live game.

    python tests/test_simulate.py     (or: pytest tests/test_simulate.py)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tftwatch.simulate import simulate          # noqa: E402


def _actions(res):
    return {s["name"]: s["action"] for s in res["shop"]}


def test_commits_comp_from_board_and_recommends_oncomp_pairs():
    res = simulate(["Caitlyn", "Briar", "Rek'Sai"],
                   ["Meeple", "Teemo", "Caitlyn", "Rek'Sai", "Briar"],
                   gold=20, stage="2-7", level=5)
    # board is Primordian-heavy -> it commits to Primordian Jinx
    assert res["comp"] and res["comp"]["name"] == "Primordian Jinx"
    acts = _actions(res)
    # on-comp Primordian pairs -> buy; off-comp Caitlyn -> dropped once the comp commits
    assert acts["Rek'Sai"] == "buy" and acts["Briar"] == "buy"
    assert acts["Caitlyn"] != "buy"
    # a non-champion name is reported, not silently treated as a unit
    assert "Meeple" in res["unresolved"]


def test_contested_unit_in_shop_flags_deny():
    res = simulate(["Jinx", "Rek'Sai"], ["Jinx", "Vex", "Akali", "Leona", "Jhin"],
                   gold=30, comp_key="primordian_jinx", contested=["Vex", "Jhin"])
    acts = _actions(res)
    assert acts["Vex"] == "deny" and acts["Jhin"] == "deny"   # contested opponent carries
    assert acts["Jinx"] == "buy"                              # your own carry, never deny


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

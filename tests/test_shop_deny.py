"""Contest-denial: a heavily-contested OPPONENT unit showing in YOUR shop is flagged as a
'deny' buy (buy + bench to starve the teams chasing it). The safe, public-info version of
sniping — it uses lobby contest, never hidden opponent copy-counts.

    python tests/test_shop_deny.py     (or: pytest tests/test_shop_deny.py)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tftwatch.coach import CoachRoland                # noqa: E402
from tftwatch import compguide                         # noqa: E402


def _view(contested, gold=20):
    coach = CoachRoland()
    comp = compguide.comp_detail("primordian_jinx")    # carry Jinx; early Rek'Sai/Bel'Veth/Akali
    shop = [{"name": "Jhin", "cost": 5}, {"name": "Veigar", "cost": 1},
            {"name": "Rek'Sai", "cost": 1}, {"name": "Jinx", "cost": 4}]
    return {v["name"]: v for v in coach.shop_plan(shop, comp, gold=gold, contested=contested)}


def test_contested_offcomp_unit_flags_deny():
    v = _view(["Jhin"])
    assert v["Jhin"]["action"] == "deny" and v["Jhin"]["role"] == "deny"


def test_uncontested_offcomp_unit_is_not_flagged():
    assert _view(["Jhin"])["Veigar"]["action"] is None


def test_your_own_unit_stays_a_buy_even_if_contested():
    v = _view(["Jinx", "Jhin"])                        # your carry is contested too
    assert v["Jinx"]["action"] == "buy" and v["Jinx"]["role"] == "carry"   # yours, never deny
    assert v["Rek'Sai"]["action"] == "buy"                                 # comp piece, not deny


def test_deny_skipped_when_unaffordable():
    assert _view(["Jhin"], gold=2)["Jhin"]["action"] is None   # Jhin costs 5, can't afford


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

"""Fast, deterministic tests for the coach's pure logic — no screen, vision, or API.

These cover the parts that have silently broken before (recipe/cost lookups, the
2-star math, item/holder/econ advice). Run either way:
    python tests/test_logic.py
    pytest tests/test_logic.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tftwatch import cdragon, compguide          # noqa: E402
from tftwatch.coach import CoachRoland            # noqa: E402

coach = CoachRoland()


def test_cost_of_uses_current_set():
    # Names collide across sets; cost_of must use the CURRENT set (Jhin is 5, not 4).
    assert cdragon.cost_of("Jhin") == 5
    assert cdragon.cost_of("Caitlyn") == 1
    assert cdragon.cost_of("not a champion") is None


def test_item_recipe_from_cdragon():
    parts = [p.lower() for p in cdragon.item_components("Infinity Edge")]
    assert "b.f. sword" in parts and "sparring gloves" in parts


def test_two_copies_is_not_a_two_star():
    shop = [{"name": "Caitlyn", "cost": 1}, {"name": "Caitlyn", "cost": 1},
            {"name": "Gragas", "cost": 2}]
    view = coach.shop_plan(shop, None, 9, owned=[])
    cait = [s for s in view if s["name"] == "Caitlyn"]
    assert cait and all(s["pair"] and "2/3" in (s["tostar"] or "") for s in cait)
    # owning two already -> buying the third completes the 2-star
    view2 = coach.shop_plan([{"name": "Caitlyn", "cost": 1}], None, 9,
                            owned=["Caitlyn", "Caitlyn"])
    assert "makes" in (view2[0]["tostar"] or "")


def test_gold_sequencing_locks_what_you_cant_afford():
    # Two 1-cost pairs + a partner buy, but only 1 gold: keep one, lock/skip the rest.
    shop = [{"name": "Caitlyn", "cost": 1}, {"name": "Caitlyn", "cost": 1},
            {"name": "Talon", "cost": 1}, {"name": "Talon", "cost": 1}]
    view = coach.shop_plan(shop, None, 1, owned=[])
    buys = [s for s in view if s["action"] == "buy"]
    assert len(buys) == 1                       # only 1 gold -> exactly one affordable buy


def test_item_choice_matches_carry_components():
    comp = compguide.comp_detail("dark_star_jhin")
    out = {o["name"]: o["take"] for o in
           coach.item_choice(["B.F. Sword", "Tear of the Goddess"], comp)}
    assert out["B.F. Sword"] is True            # builds Jhin's AD items
    assert out["Tear of the Goddess"] is False  # AP, wrong for him


def test_item_holder_hold_vs_slam():
    fast = coach.item_holder_advice(compguide.comp_detail("dark_star_jhin"))[0]["text"]
    reroll = coach.item_holder_advice(compguide.comp_detail("samira_reroll"))[0]["text"]
    assert "Hold" in fast and "Itemize" in reroll


def test_reroll_advice_is_stage_aware():
    early = coach.reroll_advice(4, 2, "flex", stage="2-1")[0]["text"]
    assert "too early" in early.lower()


def test_choose_god_returns_priority_pick():
    rec = coach.choose_god(["Yasuo", "Aurelion Sol"], "fast9")
    assert rec and rec[0]["priority"] >= 100 and "take" in rec[0]["text"].lower()


def test_level_pacing():
    assert "behind" in coach.level_pacing("2-1", 3, "flex")[0]["text"].lower()
    assert "curve" in coach.level_pacing("3-2", 6, "flex")[0]["text"].lower()
    assert coach.level_pacing("3-3", 6, "reroll") == []     # reroll levels on its own
    assert coach.level_pacing(None, 5, "flex") == []


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

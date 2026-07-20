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


def test_pair_math_caps_at_two_star():
    # already own 3 of a unit (a completed 2-star) -> a 4th copy isn't a pair to chase
    v = coach.shop_plan([{"name": "Caitlyn", "cost": 1}], None, 9, owned=["Caitlyn"] * 3)
    assert v[0]["pair"] is False and v[0]["tostar"] is None
    # own 2 + 1 in shop -> completes the 2-star
    v2 = coach.shop_plan([{"name": "Caitlyn", "cost": 1}], None, 9, owned=["Caitlyn"] * 2)
    assert "makes" in (v2[0]["tostar"] or "")


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


def test_trait_breakpoints_and_advice():
    assert cdragon.trait_breakpoints("Bastion") == [2, 4, 6]
    # one unit from the next breakpoint -> a rec; two away -> nothing
    assert "Bastion 2" in coach.trait_advice([{"name": "Bastion", "count": 1}])[0]["text"]
    assert coach.trait_advice([{"name": "Bastion", "count": 2}]) == []
    assert coach.trait_advice([]) == []


def test_level_pacing():
    assert "behind" in coach.level_pacing("2-1", 3, "flex")[0]["text"].lower()
    assert "curve" in coach.level_pacing("3-2", 6, "flex")[0]["text"].lower()
    assert coach.level_pacing("3-3", 6, "reroll") == []     # reroll levels on its own
    assert coach.level_pacing(None, 5, "flex") == []


def test_comp_commit_needs_a_clear_signal():
    """The 'it locked Nami off 2 Space Groove' fix: only commit on a clear line."""
    # four traits TIED at 2 = a flex board with no line -> DON'T lock a comp (the real bug)
    tie = [{"name": "Space Groove", "count": 2}, {"name": "Bastion", "count": 2},
           {"name": "Vanguard", "count": 2}, {"name": "Anima", "count": 2}]
    assert compguide.suggest_for_traits(tie, [], current_key=None) is None
    # a single UNAMBIGUOUS trait at 2 (Primordian opener) -> a real early line, commit
    one = [{"name": "Primordian", "count": 2}, {"name": "Rogue", "count": 1}]
    assert compguide.suggest_for_traits(one, [], current_key=None) is not None
    # 3 of a defining trait -> a clear signal even amid other 2s, commit
    three = [{"name": "Space Groove", "count": 3}, {"name": "Bastion", "count": 2}]
    assert compguide.suggest_for_traits(three, [], current_key=None) is not None


def test_plan_advice_is_tagged_out_of_the_live_feed():
    """Build/comp advice is 'plan' (shown in the comp panel), not 'live' feed spam."""
    comp = compguide.comp_detail("primordian_jinx")
    plan = coach.item_holder_advice(comp) + coach.early_game(comp, stage="2-3")
    assert plan and all(r.get("kind") == "plan" for r in plan)
    # a live call (scout nudge) stays in the feed
    live = coach.scout_prompt([{"name": "X", "hp": 60}], known=set())
    assert live and all(r.get("kind", "live") == "live" for r in live)


def test_postgame_review_summary():
    from tftwatch import review
    part = {
        "placement": 3, "level": 8, "last_round": 32,
        "units": [
            {"character_id": "TFT17_Jhin", "tier": 2,
             "itemNames": ["TFT_Item_InfinityEdge", "TFT_Item_LastWhisper", "TFT_Item_GuardianAngel"]},
            {"character_id": "TFT17_Caitlyn", "tier": 2, "itemNames": []},
        ],
        "traits": [{"name": "TFT17_Bastion", "num_units": 2, "style": 1}],
        "augments": [],
    }
    s = review.summarize_participant(part)
    assert s["placement"] == 3 and s["level"] == 8
    assert s["carry"]["name"] == "Jhin" and len(s["carry"]["items"]) == 3   # most items -> carry
    assert s["comp_match"]                                                   # matched a Jhin comp
    tk = review.takeaways(s)
    assert any("Placed 3" in t for t in tk) and any("Jhin" in t for t in tk)


def test_comp_progress_shopping_list():
    comp = {"name": "Test", "board": ["Jhin", "Xayah", "Aurora", "Rakan"]}
    r = coach.comp_progress(comp, owned=["Jhin", "Aurora"])[0]["text"]
    assert "2/4" in r and "Xayah" in r and "Rakan" in r
    done = coach.comp_progress(comp, owned=["Jhin", "Xayah", "Aurora", "Rakan"])[0]["text"]
    assert "complete" in done.lower()
    assert coach.comp_progress(None, ["Jhin"]) == []


def test_purchase_tracker_infers_buys():
    from tftwatch.tracker import PurchaseTracker
    t = PurchaseTracker()
    t.update(["Talon", "Caitlyn", "Zoe", "Jax", "Illaoi"], gold=5)
    t.update(["Talon", "Zoe", "Jax", "Illaoi"], gold=4)        # Caitlyn left + gold drop -> buy
    assert t.owned().count("Caitlyn") == 1
    t.update(["Gnar", "Vex", "Nami", "Poppy", "Fizz"], gold=2)  # whole shop changed -> reroll, ignore
    assert "Gnar" not in t.owned()
    t.update(["Vex", "Nami", "Poppy", "Fizz"], gold=1)         # Gnar left + gold drop -> buy
    assert t.owned().count("Gnar") == 1
    t.update(["Vex", "Nami", "Poppy"], gold=1)                 # Fizz gone but gold same -> not a buy
    assert "Fizz" not in t.owned()


def test_ledger_accumulates_contest():
    from tftwatch.ledger import Ledger
    L = Ledger()
    L.note_carry("A", "Jhin"); L.note_carry("B", "Mordekaiser"); L.note_carry("C", "Jhin")
    assert L.contested_carries() == ["Jhin"]                 # 2 on Jhin, 1 on Morde
    L.note_carry("D", "Mordekaiser")
    assert L.contested_carries() == ["Jhin", "Mordekaiser"]  # now both contested
    L.note_carry("C", "Mordekaiser")                         # C pivots off Jhin
    assert L.contested_carries() == ["Mordekaiser"]          # Jhin no longer 2+


def test_comp_traits_and_items_are_real():
    import json
    real_traits = {t.lower() for t in cdragon.current_traits()}
    data = json.loads(cdragon.DATA_FILE.read_text(encoding="utf-8"))
    def norm(s): return "".join(c for c in (s or "").lower() if c.isalnum())
    items = {norm(it["name"]) for it in data.get("items", []) if it.get("name")}
    for key, c in compguide.COMPS.items():
        for t in (c.get("traits") or []):
            assert t.lower() in real_traits, f"{key}: trait '{t}' isn't a real Set trait"
        for it in (c.get("carry_items") or []):
            n = norm(it)
            ok = n in items or any((len(n) >= 5 and (n in k or k in n)) for k in items)
            assert ok, f"{key}: carry item '{it}' isn't a real item"


def test_comp_boards_have_real_units():
    summons = {"ivern minion", "galio"}      # legit summoned board units (not shoppable champs)
    for key, c in compguide.COMPS.items():
        for u in (c.get("final_board") or []):
            assert u.lower() in summons or cdragon.champ_traits(u), f"{key}: '{u}' is not a real unit"


def test_choose_god_prefers_fit_low_variance():
    rec = coach.choose_god(["Thresh", "Soraka"], "fast9")[0]   # Soraka fits fast9 + low variance
    assert "Soraka" in rec["text"]
    assert rec["priority"] >= 100 and rec["timer"]             # a timed pick, pinned to top


def test_choose_augment_emblem_for_your_trait():
    recs = coach.choose_augment(["Space Groove Emblem", "Cluttered Mind"],
                                stage="3-2", traits=["Space Groove"])
    assert "Space Groove Emblem" in recs[0]["text"]            # emblem that points your comp wins


def test_board_from_traits_credits_comp_units():
    import re
    comp = compguide.comp_detail("space_groove")
    rec = coach.comp_progress(comp, owned=[], traits=[{"name": "Space Groove", "count": 5}])[0]
    got = int(re.search(r"(\d+)/\d+", rec["text"]).group(1))   # credited from traits, no tracker
    assert got >= 4


def test_augment_name_index_resolves_spaceless_ocr():
    # OCR collapses card-title spaces ("Apotheotic Forge" -> "ApotheoticForge"), so the augment
    # index must resolve the alnum-normalized key. Regression for the reader reading nothing.
    idx = cdragon.augment_name_index()
    assert idx.get("apotheoticforge") == "Apotheotic Forge"   # tft17_ set-specific
    assert idx.get("glasscannonii") == "Glass Cannon II"      # generic tft_ (cross-set), was missing
    assert idx.get("portableforge") == "Portable Forge"       # base tier preferred over "++"
    assert len(idx) > 400                                     # full pool, not just ~53 tft17_
    assert len(cdragon.current_set_augments()) > 200          # generic augments now included too


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

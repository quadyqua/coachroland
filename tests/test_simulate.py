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


def test_early_game_advice_suppressed_in_late_game():
    board, shop = ["Twisted Fate", "Jax"], ["Twisted Fate", "Caitlyn", "Aatrox", "Corki", "Diana"]
    early = simulate(board, shop, gold=8, level=4, stage="2-1", comp_key="fateweaver_tf")
    late = simulate(board, shop, gold=40, level=9, stage="5-2", comp_key="fateweaver_tf")
    assert any(a["text"].startswith("EARLY") for a in early["advice"])       # shown in the early game
    assert not any(a["text"].startswith("EARLY") for a in late["advice"])    # stale by stage 5 -> suppressed


def test_low_hp_triggers_roll_to_stabilize():
    shop = ["Jinx", "Vex", "Akali", "Leona", "Jhin"]
    dying = simulate(["Jinx"], shop, gold=40, hp=2, comp_key="primordian_jinx", stage="4-6", level=8)
    healthy = simulate(["Jinx"], shop, gold=40, hp=60, comp_key="primordian_jinx", stage="4-6", level=8)
    # at 2 HP with gold, override econ -> a loud "roll it down" call
    assert dying["econ"] and dying["econ"][0]["severity"] == "danger"
    assert "roll" in dying["econ"][0]["text"].lower()
    # healthy player keeps normal econ (not the desperation override)
    assert healthy["econ"] and "roll it all" not in healthy["econ"][0]["text"].lower()


def test_single_rival_warns_multi_defers():
    args = dict(comp_key="primordian_jinx", stage="4-2", level=8, gold=30)
    board, shop = ["Jinx", "Rek'Sai"], ["Jinx", "Vex", "Akali", "Leona", "Jhin"]

    def has(res, sub):
        return any(sub.lower() in a["text"].lower() for a in res["advice"])

    assert not has(simulate(board, shop, rivals=[], **args), "also on")              # nobody -> quiet
    one = simulate(board, shop, rivals=["TheJim"], **args)
    assert has(one, "thejim is also on jinx")                                        # 1 -> named warn
    two = simulate(board, shop, rivals=["TheJim", "LooShiba"], **args)
    assert not has(two, "also on")                                                   # 2+ -> single-warn defers
    assert has(two, "avoid forcing")                                                 # 2+ -> multi danger fires


def test_roll_timing_uses_shop_odds():
    def econ(ck, lvl, gold):
        r = simulate(["Aatrox"], ["Aatrox", "Leona", "Kai'Sa", "Vex", "Jinx"],
                     gold=gold, level=lvl, stage="4-2", comp_key=ck)
        return r["econ"][0]["text"].lower() if r["econ"] else ""

    assert "level to 8" in econ("mecha_sol", 6, 40)     # 4-cost, too low -> level up first
    assert "roll now" in econ("mecha_sol", 8, 55)       # 4-cost, at level + gold -> roll
    assert "stop leveling" in econ("nova_reroll", 8, 50)  # 1-cost over-leveled -> odds dropping


def test_hard_switch_only_when_contested():
    shop = ["Jinx", "Vex", "Akali", "Leona", "Jhin"]

    def switched(res):
        return any("hard-switch" in a["text"].lower() for a in res["advice"])

    # carry contested (2 rivals) + at a level to hit an open line -> suggest a pivot
    assert switched(simulate(["Jinx"], shop, gold=40, level=7, stage="4-2",
                             comp_key="primordian_jinx", rivals=["A", "B"]))
    # your line is uncontested -> never suggest abandoning it
    assert not switched(simulate(["Jinx"], shop, gold=40, level=7, stage="4-2",
                                 comp_key="primordian_jinx", rivals=[]))


def test_stabilize_gives_concrete_steps_when_bleeding():
    shop = ["Jinx", "Vex", "Akali", "Leona", "Jhin"]

    def why(hp, lvl, gold):
        r = simulate(["Jinx", "Rek'Sai"], shop, gold=gold, level=lvl, stage="5-2",
                     comp_key="primordian_jinx", hp=hp)
        s = [a for a in r["advice"] if "stabilize" in a["text"].lower()]
        return s[0]["why"].lower() if s else ""

    bleeding = why(20, 6, 30)
    assert "slam" in bleeding and "positioning" in bleeding   # free wins: items + position
    assert "level 8" in bleeding and "roll" in bleeding       # under-leveled + gold -> XP then roll
    onlevel_nogold = why(24, 8, 5)
    assert "buy xp" not in onlevel_nogold and "roll" not in onlevel_nogold   # nothing to spend
    assert why(72, 8, 40) == ""                                # healthy -> silent


def test_carry_item_builds_have_no_duplicates():
    from tftwatch import compguide
    for key, c in compguide.COMPS.items():
        items = c.get("carry_items") or []
        assert len(items) == len(set(items)), f"{key} has duplicate items: {items}"


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

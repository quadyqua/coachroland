"""Tier-2 robustness regression tests: the in-game gate + HP-read sanity.

Real captured frames; no live game or network needed.

    python tests/test_ingame_and_hp.py     (or: pytest tests/test_ingame_and_hp.py)
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tftwatch import localvision as lv          # noqa: E402
from tftwatch.watcher import _smooth_hp          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fx(name):
    return os.path.join(ROOT, "fixtures", name)


def test_in_game_true_for_real_game_frames():
    assert lv.in_game(_fx("lobby_8p.jpg")) is True
    assert lv.in_game(_fx("panel_damage.jpg")) is True     # a detail card is still in-game


def test_not_in_game_for_client_screen():
    # The client/desktop (friends list, clock) has no stage indicator -> not a game.
    assert lv.in_game(_fx("notgame_client.jpg")) is False


def test_hp_never_shared_by_three_or_more():
    # Regression for the "five players all at 16 HP" bug: no HP value may back 3+ players
    # (Double Up teams share HP, but only in pairs).
    players = lv.read_lobby(_fx("lobby_8p.jpg"))["players"]
    counts = collections.Counter(p["hp"] for p in players if p.get("hp") is not None)
    shared = {hp: n for hp, n in counts.items() if n > 2}
    assert not shared, f"HP fabricated across 3+ players: {shared}"


def test_smooth_hp_fills_none_from_history():
    hist = {"Alice": 50}
    players = [{"name": "Alice", "hp": None}, {"name": "Bob", "hp": None}]
    _smooth_hp(players, hist)
    assert players[0]["hp"] == 50       # unread HP kept from last known value
    assert players[1]["hp"] is None     # no history -> honest unknown, not fabricated


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

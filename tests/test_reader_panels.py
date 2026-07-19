"""Regression tests for the lobby reader's DETAIL-PANEL handling.

The right-side region also hosts two cards that overlay the player list:
  - the per-player "Damage Dealt" breakdown (when you click a player), and
  - the unit-detail card (when you select your own unit).
Both used to be misread as opponents ("VS", "Damage Dealt", "Sell for", trait labels
like "Bulwark"/"Bastion"). These are REAL captured frames that guard that fix.

    python tests/test_reader_panels.py     (or: pytest tests/test_reader_panels.py)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tftwatch import localvision as lv          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fx(name):
    return os.path.join(ROOT, "fixtures", name)


def _names(path):
    return [p["name"] for p in lv.read_lobby(_fx(path))["players"] if p.get("name")]


# Junk tokens that should NEVER surface as a player name (UI labels / trait names).
_JUNK = {"vs", "damage", "dealt", "sell", "hex", "front", "back",
         "bulwark", "bastion", "timebreaker", "fighter", "magic", "online"}


def test_clean_lobby_reads_real_names():
    names = _names("lobby_8p.jpg")
    for expected in ("TheJim", "YourHateAmuses", "LooShiba", "Dumbdummm"):
        assert expected in names, f"{expected!r} missing — got {names}"


def test_damage_panel_not_read_as_players():
    names = _names("panel_damage.jpg")
    assert names == [], f"damage-dealt panel should yield no players, got {names}"


def test_unit_detail_panel_not_read_as_players():
    names = _names("panel_unitdetail.jpg")
    assert names == [], f"unit-detail panel should yield no players, got {names}"


def test_no_junk_tokens_in_any_frame():
    for frame in ("lobby_8p.jpg", "panel_damage.jpg", "panel_unitdetail.jpg"):
        for name in _names(frame):
            low = name.lower()
            assert not any(j in low for j in _JUNK), f"junk name {name!r} in {frame}"


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

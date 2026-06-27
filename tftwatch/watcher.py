"""Background lobby watcher — fully automatic, no manual screenshots.

Continuously samples the right-side player-list region in memory (via mss). Frames
are NEVER written to disk during play; only when the panel meaningfully changes and
settles does it read the lobby, then hand the read to Coach Roland for advice.

Capture hygiene: a managed temp dir is purged at startup, after every game, and on
exit. Coach Roland's short-term analysis is in-memory only and reset per game, so
nothing piles up.

    python -m tftwatch.watcher          # live watch (needs the game on screen)
    python -m tftwatch.watcher --once   # save one panel crop for region tuning, NO API call
"""
import sys
import time
import atexit

import mss
import numpy as np
from PIL import Image

from .vision import read_lobby_pil, _crop_region, RIGHT_PANEL
from .coach import CoachRoland
from .cleanup import capture_dir, purge_captures


def _grab_full(sct, monitor) -> Image.Image:
    shot = sct.grab(monitor)
    return Image.frombytes("RGB", shot.size, shot.rgb)


def _signature(full_img: Image.Image) -> np.ndarray:
    """Tiny grayscale fingerprint of the panel region for cheap change detection."""
    panel = _crop_region(full_img, RIGHT_PANEL)
    small = panel.convert("L").resize((24, 64))
    return np.asarray(small, dtype=np.int16)


def _changed(a, b, threshold: float = 6.0) -> bool:
    if a is None or b is None:
        return True
    return float(np.abs(a - b).mean()) > threshold


def watch(poll: float = 1.0, settle: float = 1.0, min_gap: float = 6.0,
          model: str = "gpt-4o", on_update=None) -> None:
    """Watch the panel; read + coach when it changes and settles.

    on_update(dict) — optional callback fed each read/game-over (used by the
    dashboard). When omitted, results print to the terminal.
    """
    purge_captures()                       # start clean
    atexit.register(purge_captures)        # leave clean
    coach = CoachRoland()
    print("TFTwatch + Coach Roland running. Just play — it reads on its own. Ctrl+C to stop.\n")

    last_sig = None
    pending_since = None
    last_read = 0.0
    empty_reads = 0                        # consecutive 'no lobby' reads -> game over

    with mss.MSS() as sct:
        monitor = sct.monitors[1]          # primary display
        try:
            while True:
                full = _grab_full(sct, monitor)
                sig = _signature(full)
                now = time.time()

                if _changed(last_sig, sig):
                    last_sig = sig
                    pending_since = now    # change seen; wait for it to settle
                elif pending_since and (now - pending_since) >= settle and (now - last_read) >= min_gap:
                    pending_since = None
                    last_read = now
                    try:
                        data = read_lobby_pil(full, model=model)
                    except Exception as e:
                        print(f"  (read failed: {e})")
                        time.sleep(poll)
                        continue

                    players = data.get("players") or []
                    if len(players) < 2:
                        # Panel not present -> probably between games / in menu
                        empty_reads += 1
                        if empty_reads >= 2:
                            coach.reset()
                            removed = purge_captures()
                            if on_update:
                                on_update({"ts": time.strftime('%H:%M:%S'), "event": "game_over",
                                           "data": None, "advice": []})
                            else:
                                print(f"[{time.strftime('%H:%M:%S')}] Game over — cleared Coach Roland's "
                                      f"session memory; removed {removed} temp file(s).\n")
                            empty_reads = 0
                        time.sleep(poll)
                        continue

                    empty_reads = 0
                    advice = coach.observe(data)
                    stamp = time.strftime('%H:%M:%S')
                    if on_update:
                        on_update({"ts": stamp, "event": "read", "data": data, "advice": advice})
                    elif advice:
                        print(f"[{stamp}]\n{coach.say(advice)}\n")
                    else:
                        print(f"[{stamp}] lobby read — no new threats.\n")
                time.sleep(poll)
        except KeyboardInterrupt:
            removed = purge_captures()
            print(f"\nstopped. removed {removed} temp file(s).")


def _once() -> None:
    """Capture one frame + save the panel crop to the managed temp dir. No API call."""
    out = capture_dir() / "panel_capture.png"
    with mss.MSS() as sct:
        full = _grab_full(sct, sct.monitors[1])
    print(f"captured full screen: {full.size}")
    _crop_region(full, RIGHT_PANEL).save(out)
    print(f"saved panel crop -> {out}\n(open it to check the region framing; it's auto-purged on next run)")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    if "--once" in sys.argv:
        _once()
    else:
        watch()

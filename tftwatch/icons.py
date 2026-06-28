"""Free champion recognition by portrait — no OCR, no API.

CDragon ships every champion's HUD square tile (the same art shown on the bench
and board). We cache those tiles once, then match an on-screen slot crop against
them by normalized cross-correlation. Recognizing the portrait gives us the name
AND the cost (from cdragon), so the bench can be read live at $0.

Region/threshold need tuning against a real in-game frame; identify() is robust to
brightness (zero-mean, unit-norm vectors) but not to heavy overlays.
"""
from pathlib import Path
import urllib.request

import numpy as np
from PIL import Image

from . import cdragon

CACHE = Path(__file__).resolve().parent.parent / ".cache" / "icons"
SIZE = 32                 # templates + crops compared at this resolution
MATCH_THRESHOLD = 0.50    # min cross-correlation to accept a match (tune on a real frame)

_templates = None         # [(name, cost, vec)] loaded once


def _norm_vec(pil: "Image.Image") -> np.ndarray:
    """SIZE x SIZE RGB -> zero-mean unit-norm vector (brightness-robust correlation)."""
    a = np.asarray(pil.convert("RGB").resize((SIZE, SIZE)), dtype=np.float32).ravel()
    a -= a.mean()
    n = np.linalg.norm(a)
    return a / n if n > 1e-6 else a


def _fetch(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "tftwatch"})
    with urllib.request.urlopen(req, timeout=20) as r:
        dest.write_bytes(r.read())


def _load_templates():
    global _templates
    if _templates is not None:
        return _templates
    _templates = []
    CACHE.mkdir(parents=True, exist_ok=True)
    for c in cdragon.current_set_champions():
        f = CACHE / f"{c['api'] or c['name']}.png"
        if not f.exists():
            try:
                _fetch(c["tile_url"], f)
            except Exception:
                continue
        try:
            _templates.append((c["name"], c["cost"], _norm_vec(Image.open(f))))
        except Exception:
            continue
    return _templates


STAR_BAND = (0.0, 0.60, 1.0, 0.82)   # vertical slice of a unit tile where star pips sit; tune


def count_stars(unit_pil: "Image.Image"):
    """Best-effort 1/2/3-star count from the pip row on a unit tile, or None.

    Star pips are bright + warm (bronze/silver/gold), so we threshold bright warm
    pixels in the STAR_BAND and count runs of 'on' columns = number of pips. Heuristic;
    STAR_BAND + thresholds must be tuned against a real frame (see calibrate CLI)."""
    a = np.asarray(unit_pil.convert("RGB"), dtype=np.float32)
    h, w = a.shape[:2]
    l, t, r, b = STAR_BAND
    band = a[int(h * t):int(h * b), int(w * l):int(w * r), :]
    if band.size == 0:
        return None
    bright = (band.max(axis=2) > 175) & (band[:, :, 0] >= band[:, :, 2] - 10)  # warm + bright
    col_on = bright.mean(axis=0) > 0.25
    runs, prev = 0, False
    for v in col_on:
        if v and not prev:
            runs += 1
        prev = bool(v)
    return max(1, min(3, runs)) if runs else None


def identify(pil: "Image.Image", threshold: float = MATCH_THRESHOLD):
    """Best {name, cost, score} for a champion-portrait crop, or None below threshold."""
    tpls = _load_templates()
    if not tpls:
        return None
    v = _norm_vec(pil)
    best, score = None, -1.0
    for name, cost, vec in tpls:
        s = float(np.dot(v, vec))
        if s > score:
            best, score = (name, cost), s
    if best is None or score < threshold:
        return None
    return {"name": best[0], "cost": best[1], "score": round(score, 3)}


# ---- generic icon matching (items, augments) — same technique, free -------------
_KIND: dict = {}   # kind -> [(name, vec)]

_SOURCES = {
    "item": lambda: [(i["name"], i["icon_url"], i["api"]) for i in cdragon.current_set_items()],
    "augment": lambda: [(a["name"], a["icon_url"], a["api"]) for a in cdragon.current_set_augments()],
}


def _load_kind(kind: str):
    if kind in _KIND:
        return _KIND[kind]
    out = []
    d = CACHE / kind
    d.mkdir(parents=True, exist_ok=True)
    for name, url, key in _SOURCES[kind]():
        f = d / f"{key}.png"
        if not f.exists():
            try:
                _fetch(url, f)
            except Exception:
                continue
        try:
            out.append((name, _norm_vec(Image.open(f))))
        except Exception:
            continue
    _KIND[kind] = out
    return out


def identify_kind(pil: "Image.Image", kind: str, threshold: float = 0.45):
    """Best {name, score} for an item/augment icon crop, or None below threshold."""
    tpls = _load_kind(kind)
    if not tpls:
        return None
    v = _norm_vec(pil)
    best, score = None, -1.0
    for name, vec in tpls:
        s = float(np.dot(v, vec))
        if s > score:
            best, score = name, s
    return {"name": best, "score": round(score, 3)} if best and score >= threshold else None

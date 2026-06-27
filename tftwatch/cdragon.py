"""Community Dragon static-data resolver.

CDragon datamines the game files Riot ships and re-hosts them as free public
JSON (no key, no rate limit). We use it to turn the API's cryptic IDs into real
display names + champion costs:

    TFT17_Astronaut -> "Meeple"        (trait name)
    TFT14_Jinx      -> "Jinx", cost 4  (champion name + cost)

The 25 MB blob is downloaded once and cached on disk; lookups are in-memory.
If the download ever fails (offline), every resolver falls back to the
best-effort humanizer so the app still runs.
"""
import json
import time
import pathlib

import requests

from .names import humanize

DATA_URL = "https://raw.communitydragon.org/latest/cdragon/tft/en_us.json"
CACHE_DIR = pathlib.Path(__file__).resolve().parent.parent / ".cache" / "cdragon"
DATA_FILE = CACHE_DIR / "tft_en_us.json"
MAX_AGE_SECONDS = 7 * 24 * 3600  # refresh weekly (sets/patches change)

_champ_name: dict[str, str] = {}
_champ_cost: dict[str, int] = {}
_trait_name: dict[str, str] = {}
_loaded = False


def _download() -> dict:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fresh = DATA_FILE.exists() and (time.time() - DATA_FILE.stat().st_mtime) < MAX_AGE_SECONDS
    if not fresh:
        try:
            resp = requests.get(DATA_URL, timeout=90)
            resp.raise_for_status()
            DATA_FILE.write_bytes(resp.content)
        except Exception:
            if not DATA_FILE.exists():
                raise  # no cache and no network -> caller falls back to humanize
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def _load() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        data = _download()
    except Exception:
        return  # leave maps empty -> humanize fallback everywhere
    for s in data.get("setData", []):
        for c in s.get("champions", []):
            api = c.get("apiName")
            if not api:
                continue
            _champ_name[api] = c.get("name") or humanize(api)
            if c.get("cost") is not None:
                _champ_cost[api] = c["cost"]
        for t in s.get("traits", []):
            api = t.get("apiName")
            if api:
                _trait_name[api] = t.get("name") or humanize(api)


def champ_name(api: str) -> str:
    _load()
    return _champ_name.get(api) or humanize(api)


def champ_cost(api: str) -> int:
    _load()
    return _champ_cost.get(api, 0)


def trait_name(api: str) -> str:
    _load()
    return _trait_name.get(api) or humanize(api)

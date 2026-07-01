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
    # champion costs by display name — names collide across sets, so use the CURRENT set only
    latest = max(data.get("setData", []), key=lambda s: s.get("number") or 0, default=None)
    if latest:
        for c in latest.get("champions", []):
            if c.get("name") and c.get("cost") is not None:
                _champ_cost_by_name[c["name"].lower()] = c["cost"]
    # items are top-level (shared across sets) — build completed-item -> components recipe
    item_name = {it["apiName"]: it.get("name") for it in data.get("items", []) if it.get("apiName")}
    for it in data.get("items", []):
        comp, nm = it.get("composition"), it.get("name")
        if comp and nm:
            parts = [item_name.get(c) for c in comp if item_name.get(c)]
            if parts:
                _item_components[nm.lower()] = parts


_roster: list[str] = []
_item_components: dict = {}        # completed item name (lower) -> [component display names]
_champ_cost_by_name: dict = {}     # champion display name (lower) -> cost (1-5)


def cost_of(name: str):
    """Gold cost of a champion by display name (1-5), or None if unknown."""
    _load()
    return _champ_cost_by_name.get((name or "").lower())


def item_components(name: str) -> list:
    """Component display names that build a completed item (from CDragon recipes)."""
    _load()
    return _item_components.get((name or "").lower(), [])


def current_roster() -> list[str]:
    """Display names of the playable champions in the CURRENT TFT set.

    Used to CONSTRAIN vision reads to the real roster so the model can't hallucinate
    a champion — it must pick a name that actually exists this set. Returns [] if the
    CDragon data isn't available (offline), in which case reads stay unconstrained.
    """
    _load()
    if _roster:
        return _roster
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        sets = data.get("setData", [])
        latest = max(sets, key=lambda s: s.get("number") or 0)
        names = sorted({c.get("name") for c in latest.get("champions", [])
                        if c.get("name") and c.get("cost") and c.get("traits")})
        _roster.extend(names)
    except Exception:
        pass
    return _roster


_ASSET_BASE = "https://raw.communitydragon.org/latest/game/"


def _tile_url(tile_icon: str) -> str:
    """CDragon serves the .tex HUD tile as a .png at a lowercased game-asset path."""
    return _ASSET_BASE + tile_icon.lower().replace(".tex", ".png")


_set_champs: list[dict] = []


def current_set_champions() -> list[dict]:
    """Current-set playable champions: [{name, cost, api, tile_url}] for icon matching."""
    if _set_champs:
        return _set_champs
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        latest = max(data.get("setData", []), key=lambda s: s.get("number") or 0)
        for c in latest.get("champions", []):
            if c.get("name") and c.get("cost") and c.get("traits") and c.get("tileIcon"):
                _set_champs.append({"name": c["name"], "cost": c["cost"],
                                    "api": c.get("apiName"), "tile_url": _tile_url(c["tileIcon"])})
    except Exception:
        pass
    return _set_champs


_set_items: list[dict] = []
_set_augments: list[dict] = []


def current_set_items() -> list[dict]:
    """Standard item pool (components + completed) as [{name, api, icon_url}] for matching
    offered items by icon. Restricted to TFT_Item_* so we don't match 3000 odd assets."""
    if _set_items:
        return _set_items
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        for it in data.get("items", []):
            api = it.get("apiName") or ""
            if it.get("name") and it.get("icon") and api.startswith("TFT_Item_"):
                _set_items.append({"name": it["name"], "api": api, "icon_url": _tile_url(it["icon"])})
    except Exception:
        pass
    return _set_items


def current_set_augments() -> list[dict]:
    """Current-set augments as [{name, api, icon_url}] for matching the 3 offered by icon."""
    if _set_augments:
        return _set_augments
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        num = max(data.get("setData", []), key=lambda s: s.get("number") or 0).get("number")
        pref = f"tft{num}"
        for it in data.get("items", []):
            api = (it.get("apiName") or "").lower()
            if it.get("name") and it.get("icon") and "augment" in api and api.startswith(pref):
                _set_augments.append({"name": it["name"], "api": it["apiName"],
                                      "icon_url": _tile_url(it["icon"])})
    except Exception:
        pass
    return _set_augments


_trait_bps: dict = {}        # trait display name (lower) -> sorted [minUnits breakpoints]


def trait_breakpoints(name: str) -> list:
    """Active-unit breakpoints for a current-set trait, e.g. Bastion -> [2, 4, 6]."""
    if not _trait_bps:
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            latest = max(data.get("setData", []), key=lambda s: s.get("number") or 0)
            for t in latest.get("traits", []):
                nm = t.get("name")
                if not nm:
                    continue
                bps = sorted({e.get("minUnits") for e in (t.get("effects") or [])
                              if e.get("minUnits")})
                if bps:
                    _trait_bps[nm.lower()] = bps
        except Exception:
            pass
    return _trait_bps.get((name or "").lower(), [])


_traits_list: list[str] = []


def current_traits() -> list[str]:
    """Display names of the CURRENT set's traits — used to constrain the trait-panel read
    to REAL traits, filtering OCR junk / player names that bleed into the region."""
    _load()
    if _traits_list:
        return _traits_list
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        latest = max(data.get("setData", []), key=lambda s: s.get("number") or 0)
        _traits_list.extend(sorted({t.get("name") for t in latest.get("traits", []) if t.get("name")}))
    except Exception:
        pass
    return _traits_list


_champ_traits: dict = {}    # champion display name (lower) -> [trait display names], current set


def _norm(s: str) -> str:
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def champ_traits(name: str) -> list:
    """Trait display names of a champion in the current set — used to explain WHY a unit is
    in your comp (does it share your comp's trait, or is it just a frontline body?).

    Fuzzy-matches the name so a comp's "Nunu" still resolves CDragon's "Nunu & Willump"."""
    if not _champ_traits:
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            latest = max(data.get("setData", []), key=lambda s: s.get("number") or 0)
            for c in latest.get("champions", []):
                if c.get("name"):
                    _champ_traits[c["name"].lower()] = list(c.get("traits") or [])
        except Exception:
            pass
    key = (name or "").lower()
    if key in _champ_traits:
        return _champ_traits[key]
    kn = _norm(name)                       # fuzzy: "Nunu" -> "Nunu & Willump"
    if len(kn) >= 4:
        for k, v in _champ_traits.items():
            kk = _norm(k)
            if kn == kk or kn in kk or kk in kn:
                return v
    return []


def champ_name(api: str) -> str:
    _load()
    return _champ_name.get(api) or humanize(api)


def champ_cost(api: str) -> int:
    _load()
    return _champ_cost.get(api, 0)


def trait_name(api: str) -> str:
    _load()
    return _trait_name.get(api) or humanize(api)

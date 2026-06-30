"""Local, FREE lobby reader — RapidOCR + geometry, no API call.

Drop-in alternative to vision.read_lobby_pil: returns the same
{players:[{name,hp,unit,stars,is_self}], next_opponent} shape, but runs offline at
~$0 and near-instant. Each player row has exactly one HP number, so HP boxes are the
row anchors; the nearest name token (to the left) and any roster-matched champion
token attach to each row. The viewer's own row is the one with an HP but no name.

Honest limits vs the LLM reader (these are ICONS, not text, so OCR can't read them):
  - star pips (stars) — left null; a pixel/template pass can add them later
  - the crossed-swords NEXT-opponent marker — left null
Everything text (names, HP, spiked champ) reads locally and free.
"""
import re

import numpy as np
from PIL import Image

from . import cdragon, compguide, icons

RIGHT_PANEL = (0.78, 0.08, 1.0, 0.97)
UPSCALE = 2

_ocr = None


def _engine():
    global _ocr
    if _ocr is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr = RapidOCR()
    return _ocr


def _crop(img: "Image.Image", crop=RIGHT_PANEL) -> "Image.Image":
    w, h = img.size
    l, t, r, b = crop
    c = img.crop((int(w * l), int(h * t), int(w * r), int(h * b)))
    if UPSCALE != 1:
        c = c.resize((c.width * UPSCALE, c.height * UPSCALE))
    return c


def _boxes(pil: "Image.Image") -> list[dict]:
    res, _ = _engine()(np.array(pil))
    out = []
    for box, txt, conf in (res or []):
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        out.append({"text": (txt or "").strip(), "conf": float(conf),
                    "cx": sum(xs) / len(xs), "cy": sum(ys) / len(ys), "x0": min(xs)})
    return [b for b in out if b["text"]]


def _is_hp(t: str) -> bool:
    return t.isdigit() and 1 <= int(t) <= 100


def _roster_match(text: str):
    """Return a roster champion name if the OCR text matches one, else None."""
    roster = cdragon.current_roster()
    if not roster or not text:
        return None
    tl = text.casefold().replace(" ", "").replace("'", "")
    for name in roster:
        nl = name.casefold().replace(" ", "").replace("'", "")
        if tl == nl or (len(tl) >= 4 and (tl in nl or nl in tl)):
            return name
    return None


def _median_gap(hp_boxes: list[dict]) -> float:
    if len(hp_boxes) < 2:
        return 320.0
    gaps = sorted(hp_boxes[i + 1]["cy"] - hp_boxes[i]["cy"] for i in range(len(hp_boxes) - 1))
    return gaps[len(gaps) // 2] or 320.0


def read_lobby_pil(img: "Image.Image", crop=RIGHT_PANEL) -> dict:
    boxes = _boxes(_crop(img, crop))
    hp_boxes = sorted((b for b in boxes if _is_hp(b["text"])), key=lambda b: b["cy"])
    gap = _median_gap(hp_boxes)
    name_tol = gap * 0.5      # a name shares the row band with its HP
    unit_tol = gap * 0.7      # the spiked champ sits a bit below the name

    def nearest_unit(cy):                          # the spiked carry on this row, if any
        for b in boxes:
            m = _roster_match(b["text"])
            if m and abs(b["cy"] - cy) <= unit_tol:
                return m
        return None

    def is_name(b):                                # a player-name token, not a champ/junk
        return (any(c.isalpha() for c in b["text"]) and len(b["text"]) >= 2
                and not _roster_match(b["text"]))

    # candidate name tokens = alphabetic, not a roster champion
    used = set()
    players = []
    for hp in hp_boxes:
        cy = hp["cy"]
        name, name_box = None, None
        for b in boxes:
            if id(b) in used or not is_name(b):
                continue
            if b["x0"] >= hp["cx"]:                # name is left of the HP number
                continue
            if abs(b["cy"] - cy) <= name_tol and (name_box is None
                                                  or abs(b["cy"] - cy) < abs(name_box["cy"] - cy)):
                name, name_box = b["text"], b
        if name_box:
            used.add(id(name_box))
        players.append({"name": name, "hp": int(hp["text"]),
                        "unit": nearest_unit(cy), "stars": None,
                        "is_self": name is None})   # the highlighted YOU row has no name

    # Double Up shows ONE HP per team (4 numbers) but 8 players, so the HP anchors above
    # miss half the names. ONLY when there are clearly more names than HP rows (the team-HP
    # layout) do we add the leftover names, sharing the nearest team HP. Standard games have
    # one HP per player, so this stays off and we don't pick up floating UI labels.
    name_count = sum(1 for b in boxes if is_name(b))
    if name_count > len(hp_boxes) + 1:
        for b in sorted((x for x in boxes if id(x) not in used and is_name(x)),
                        key=lambda b: b["cy"]):
            used.add(id(b))
            hp = min(hp_boxes, key=lambda h: abs(h["cy"] - b["cy"])) if hp_boxes else None
            players.append({"name": b["text"], "hp": int(hp["text"]) if hp else None,
                            "unit": nearest_unit(b["cy"]), "stars": None, "is_self": False})
    return {"players": players, "next_opponent": None}


def read_lobby(image_path: str, crop=RIGHT_PANEL) -> dict:
    return read_lobby_pil(Image.open(image_path).convert("RGB"), crop)


# ---- bottom HUD: shop + gold + level (free "buy this" reader) -----------------
SELF_REGION = (0.12, 0.80, 0.82, 1.0)


def read_self_pil(img: "Image.Image", crop=SELF_REGION) -> dict:
    """{gold, level, shop:[{name,cost}]}. Shop champs are the reliable part (roster
    match filters out the trait labels on the cards); gold/level are best-effort."""
    boxes = _boxes(_crop(img, crop))

    level = None
    for b in boxes:
        t = b["text"].lower().replace(".", "").replace(" ", "")
        if t.startswith("lvl") or t.startswith("lv"):
            d = "".join(c for c in t if c.isdigit())
            if d:
                level = int(d)
                break

    champs = sorted(((b["cx"], b["cy"], _roster_match(b["text"])) for b in boxes),
                    key=lambda x: x[0])
    champs = [(cx, cy, m) for cx, cy, m in champs if m]
    shop = []
    for cx, cy, name in champs:
        shop.append({"name": name, "cost": cdragon.cost_of(name)})   # authoritative cost by name, not OCR

    # gold: best-effort — the largest small integer in the top band (gold reads larger
    # than the stray 1s and level digit there). Tune later if it grabs the wrong number.
    cand = [int(b["text"]) for b in boxes
            if b["cy"] < 160 and b["text"].isdigit() and 1 <= int(b["text"]) <= 200]
    gold = max(cand) if cand else None
    return {"gold": gold, "level": level, "shop": shop}


def read_self(image_path: str, crop=SELF_REGION) -> dict:
    return read_self_pil(Image.open(image_path).convert("RGB"), crop)


# ---- left trait panel: what comp you're actually building (anti-random read) --
TRAIT_REGION = (0.0, 0.13, 0.135, 0.58)


def _trait_match(text: str):
    """Return a real current-set trait name if the OCR text matches one, else None.
    Filters out junk and player names that bleed into the trait panel region."""
    traits = cdragon.current_traits()
    if not traits or not text:
        return None
    tl = text.casefold().replace(" ", "").replace(".", "").replace("'", "")
    if len(tl) < 3:
        return None
    for name in traits:
        nl = name.casefold().replace(" ", "").replace(".", "").replace("'", "")
        if tl == nl or (len(tl) >= 4 and (tl in nl or nl in tl)):
            return name
    return None


def read_traits_pil(img: "Image.Image", crop=TRAIT_REGION) -> dict:
    """{traits:[{name,count}]}. Trait name (matched to a REAL trait) + the count below it."""
    boxes = _boxes(_crop(img, crop))
    nums = [b for b in boxes if any(c.isdigit() for c in b["text"])]
    traits = []
    for b in boxes:
        name = _trait_match(b["text"])          # only keep boxes that ARE a real trait
        if not name:
            continue
        below = [d for d in nums if 0 <= d["cy"] - b["cy"] <= 140]
        count = None
        if below:
            lead = "".join(c for c in min(below, key=lambda d: d["cy"] - b["cy"])["text"] if c.isdigit())
            count = int(lead[0]) if lead else None
        traits.append({"name": name, "count": count})
    return {"traits": traits}


def read_traits(image_path: str, crop=TRAIT_REGION) -> dict:
    return read_traits_pil(Image.open(image_path).convert("RGB"), crop)


# ---- stage / round indicator (top center, e.g. "2-1") -> free, unlocks timing advice
STAGE_REGION = (0.33, 0.0, 0.50, 0.055)   # wide on purpose: the indicator shifts with resolution
# (x~0.36 at 1440p, x~0.45 at 1080p), so frame generously and let the regex find the 'N-N'.


def read_stage_pil(img: "Image.Image", crop=STAGE_REGION) -> dict:
    """{stage:'2-1'} parsed from the top-center round text, or {stage:None}."""
    text = " ".join(b["text"] for b in _boxes(_crop(img, crop)))
    m = re.search(r"([1-9])\s*[-–—]\s*([1-9])", text)
    return {"stage": f"{m.group(1)}-{m.group(2)}" if m else None}


def read_stage(image_path: str, crop=STAGE_REGION) -> dict:
    return read_stage_pil(Image.open(image_path).convert("RGB"), crop)


# ---- item-choice screen (armory / anvil): which items are offered --------------
# Items are icons -> recognize them by icon (free), same technique as champions.
# Region/slot count need tuning on a real item-choice frame (see calibrate CLI).
ITEM_REGION = (0.18, 0.28, 0.82, 0.74)
ITEM_SLOTS = 5


def _slots_identify(img, crop, slots, kind):
    """Split a choice row into slots and icon-match each -> list of names."""
    w, h = img.size
    l, t, r, b = crop
    band = img.crop((int(w * l), int(h * t), int(w * r), int(h * b))).convert("RGB")
    sw = band.width / slots
    out = []
    for i in range(slots):
        cell = band.crop((int(i * sw), 0, int((i + 1) * sw), band.height))
        if np.asarray(cell, dtype=np.float32).std() < 12:   # ~uniform -> empty
            continue
        m = icons.identify_kind(cell, kind)
        if m:
            out.append(m["name"])
    return out


def read_items_pil(img: "Image.Image", crop=ITEM_REGION, slots=ITEM_SLOTS) -> dict:
    """{items:[name]} — offered items recognized by icon (free)."""
    return {"items": _slots_identify(img, crop, slots, "item")}


def read_items(image_path: str, crop=ITEM_REGION, slots=ITEM_SLOTS) -> dict:
    return read_items_pil(Image.open(image_path).convert("RGB"), crop, slots)


# ---- augment choice (3 cards): recognize by icon (free) ------------------------
AUGMENT_REGION = (0.18, 0.30, 0.82, 0.62)
AUGMENT_SLOTS = 3


def read_augments_pil(img: "Image.Image", crop=AUGMENT_REGION, slots=AUGMENT_SLOTS) -> dict:
    """{augments:[name]} — the 3 offered augments recognized by icon (free)."""
    return {"augments": _slots_identify(img, crop, slots, "augment")}


def read_augments(image_path: str, crop=AUGMENT_REGION, slots=AUGMENT_SLOTS) -> dict:
    return read_augments_pil(Image.open(image_path).convert("RGB"), crop, slots)


# ---- God choice ("Choose your God wisely"): the names are TEXT -> free OCR works ----
OFFER_REGION = (0.22, 0.22, 0.78, 0.66)


def read_offer_pil(img: "Image.Image", crop=OFFER_REGION) -> dict:
    """{kind:'god', options:[god names]} — the offered Gods read by OCR (free, validated)."""
    found = []
    for b in _boxes(_crop(img, crop)):
        t = b["text"].strip()
        if len(t) < 3 or len(t) > 20 or len(t.split()) > 3:   # skip description sentences
            continue
        tl = t.lower()
        for g in compguide.GODS:
            gl = g.lower()
            if (tl == gl or (len(tl) >= 4 and (tl in gl or gl in tl))) and g not in found:
                found.append(g)
    return {"kind": "god", "options": found}


def read_offer(image_path: str, crop=OFFER_REGION) -> dict:
    return read_offer_pil(Image.open(image_path).convert("RGB"), crop)


# ---- bench: which units you own, by PORTRAIT (free icon match, no OCR) ----------
# Recognizing the tile tells us the champion AND its cost (cdragon), so this is the
# free, always-on "what's on my bench" read that powers pair detection.
BENCH_REGION = (0.12, 0.655, 0.58, 0.745)   # 9-slot bench row (LOCATION verified on a real frame)
# WARNING: unit RECOGNITION here does not work. CDragon-icon matching scores rendered bench tiles
# at ~noise (truth ~0.04-0.29, indistinguishable) because the in-game tile (hex mask, cost border,
# star pip, cropped splash, board bleed-through) doesn't correlate with the flat asset. Reading the
# bench needs templates/a classifier built from REAL frame crops, not CDragon assets. The watcher
# does NOT feed this into pair advice (would create false pairs). Region kept for that future work. on a real frame
BENCH_SLOTS = 9


def read_bench_pil(img: "Image.Image", crop=BENCH_REGION, slots=BENCH_SLOTS,
                   doubleup=False) -> dict:
    """{bench:[{name,cost,slot}]} — champions recognized on the bench by portrait.

    In Double Up the 9th (rightmost) bench slot is the Teamwork Cannon, not a unit
    (confirmed by watching a live Double Up game), so doubleup=True skips it."""
    w, h = img.size
    l, t, r, b = crop
    band = img.crop((int(w * l), int(h * t), int(w * r), int(h * b))).convert("RGB")
    sw = band.width / slots
    out = []
    for i in range(slots):
        if doubleup and i == slots - 1:        # 9th slot = Teamwork Cannon
            continue
        cell = band.crop((int(i * sw), 0, int((i + 1) * sw), band.height))
        if np.asarray(cell, dtype=np.float32).std() < 12:   # ~uniform -> empty slot
            continue
        m = icons.identify(cell)
        if m:
            out.append({"name": m["name"], "cost": m["cost"],
                        "stars": icons.count_stars(cell), "slot": i})
    return {"bench": out}


def read_bench(image_path: str, crop=BENCH_REGION, slots=BENCH_SLOTS, doubleup=False) -> dict:
    return read_bench_pil(Image.open(image_path).convert("RGB"), crop, slots, doubleup)


if __name__ == "__main__":
    import sys
    import json
    import os
    args = sys.argv[1:]
    if args and args[0] == "calibrate":
        # One-shot: dump every region crop + every read so all readers can be tuned
        # against ONE real in-game frame. Send me the calib/*.png + the printed output.
        path = args[1] if len(args) > 1 else "fixtures/lobby_starups_3-3.png"
        img = Image.open(path).convert("RGB")
        w, h = img.size
        os.makedirs("calib", exist_ok=True)
        regions = {"lobby": RIGHT_PANEL, "self_shop": SELF_REGION, "traits": TRAIT_REGION,
                   "bench": BENCH_REGION, "stage": STAGE_REGION, "items": ITEM_REGION}
        for nm, (l, t, r, b) in regions.items():
            img.crop((int(w * l), int(h * t), int(w * r), int(h * b))).save(f"calib/{nm}.png")
        print(f"saved {len(regions)} region crops -> calib/  (open each: does it frame the right thing?)")
        print("  stage  :", read_stage_pil(img))
        print("  self   :", read_self_pil(img))
        print("  traits :", read_traits_pil(img))
        print("  bench  :", read_bench_pil(img))
        print("  lobby  :", {"players": len(read_lobby_pil(img).get("players", []))})
    elif args and args[0] == "bench":
        # Calibration: dump the bench band + each slot's BEST match & score (no threshold),
        # so the region and accept-threshold can be tuned against a real in-game frame.
        path = args[1] if len(args) > 1 else "fixtures/lobby_starups_3-3.png"
        img = Image.open(path).convert("RGB")
        w, h = img.size
        l, t, r, b = BENCH_REGION
        band = img.crop((int(w * l), int(h * t), int(w * r), int(h * b)))
        band.save("bench_band.png")
        print(f"saved cropped bench band -> bench_band.png  (check it frames the 9 slots)")
        sw = band.width / BENCH_SLOTS
        for i in range(BENCH_SLOTS):
            cell = band.crop((int(i * sw), 0, int((i + 1) * sw), band.height))
            std = float(np.asarray(cell, dtype=np.float32).std())
            m = icons.identify(cell, threshold=0.0)
            print(f"  slot {i}: std={std:5.1f}  best={m['name'] if m else '?':16} "
                  f"score={m['score'] if m else 0}")
    else:
        path = args[0] if args else "fixtures/lobby_starups_3-3.png"
        print(json.dumps(read_lobby(path), ensure_ascii=True, indent=2))

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
import numpy as np
from PIL import Image

from . import cdragon

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

    # candidate name tokens = alphabetic, not a roster champion
    used = set()
    players = []
    for hp in hp_boxes:
        cy = hp["cy"]
        name, name_box = None, None
        for b in boxes:
            if id(b) in used or not any(c.isalpha() for c in b["text"]):
                continue
            if _roster_match(b["text"]):           # that's a unit, not a name
                continue
            if b["x0"] >= hp["cx"]:                # name is left of the HP number
                continue
            if abs(b["cy"] - cy) <= name_tol and (name_box is None
                                                  or abs(b["cy"] - cy) < abs(name_box["cy"] - cy)):
                name, name_box = b["text"], b
        unit = None
        for b in boxes:
            m = _roster_match(b["text"])
            if m and abs(b["cy"] - cy) <= unit_tol:
                unit = m
                break
        if name_box:
            used.add(id(name_box))
        players.append({"name": name, "hp": int(hp["text"]),
                        "unit": unit, "stars": None,
                        "is_self": name is None})   # the highlighted YOU row has no name
    return {"players": players, "next_opponent": None}


def read_lobby(image_path: str, crop=RIGHT_PANEL) -> dict:
    return read_lobby_pil(Image.open(image_path).convert("RGB"), crop)


if __name__ == "__main__":
    import sys
    import json
    path = sys.argv[1] if len(sys.argv) > 1 else "fixtures/lobby_starups_3-3.png"
    data = read_lobby(path)
    print(json.dumps(data, ensure_ascii=True, indent=2))

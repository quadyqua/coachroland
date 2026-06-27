"""Lobby reader — extract the TFT right-side player list from a screenshot.

Reads the fixed right-hand strip (player names, health, and any starred-up unit
shown next to a name) using OpenAI vision. This is the "eyes" of the live coach:
it turns a screen capture into structured data with zero scouting.

Capture is a single still frame (no constant recording). Only a cropped strip is
sent, not your whole screen. Uses the OpenAI key already in .env.
"""
import io
import os
import json
import base64

from PIL import Image
from openai import OpenAI

# The player list lives in the right strip of a 16:9 TFT screen. Fractions of the
# full frame: (left, top, right, bottom). Left edge stays loose because an expanded
# (starred-up) row grows leftward. Tune if your HUD scale differs.
RIGHT_PANEL = (0.78, 0.08, 1.0, 0.97)
UPSCALE = 2  # enlarge the crop before sending -> sharper digits and star pips

_PROMPT = """You are reading the right-side PLAYER LIST from a Teamfight Tactics screenshot.

Each row is one player, top to bottom. Every row shows: the player's NAME (text),
their HEALTH (a number, ~0-100), and their little-legend portrait on the far right.

IMPORTANT — read EVERY row, including the VIEWER'S OWN row, which is visually
highlighted (larger, gold/brighter frame) and usually has no name label. Mark it
with "is_self": true. All other rows have is_self false.

When a player has recently STARRED UP a notable unit, their row expands to also show
that champion's NAME plus STAR PIPS — count the small star icons carefully (1, 2, or
3). If no champion/pips are shown for a row, unit and stars are null.

One row may have a crossed-swords / versus marker = the viewer's NEXT opponent.

Return STRICT JSON, no prose:
{
  "players": [
    {"name": "<name, or null for the self row>", "hp": <int or null>,
     "unit": "<starred-up champion, or null>", "stars": <1-3 or null>,
     "is_self": <true/false>}
  ],
  "next_opponent": "<name with the crossed-swords marker, or null>"
}
Read carefully — get the HP digits and star counts exactly right. Do not invent units."""


def _client() -> OpenAI:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("No OPENAI_API_KEY found. Add it to .env.")
    return OpenAI(api_key=key)


def _crop_region(img: "Image.Image", crop=RIGHT_PANEL) -> "Image.Image":
    w, h = img.size
    l, t, r, b = crop
    region = img.crop((int(w * l), int(h * t), int(w * r), int(h * b)))
    if UPSCALE != 1:
        region = region.resize((region.width * UPSCALE, region.height * UPSCALE))
    return region


def _b64(img: "Image.Image") -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def read_lobby_pil(img: "Image.Image", model: str = "gpt-4o", crop=RIGHT_PANEL) -> dict:
    """Full-screen PIL image -> {players:[...], next_opponent}. Crops the panel itself."""
    b64 = _b64(_crop_region(img, crop))
    resp = _client().chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": _PROMPT},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}},
            ],
        }],
    )
    return json.loads(resp.choices[0].message.content)


def read_lobby(image_path: str, model: str = "gpt-4o", crop=RIGHT_PANEL) -> dict:
    """Screenshot path -> lobby data."""
    return read_lobby_pil(Image.open(image_path).convert("RGB"), model, crop)


# ---- EXPERIMENTAL: read your own board for positioning advice -----------------
# The hex board is the hardest thing to read (isometric, overlapping units). This
# is a coarse v1: rows = front/mid/back, side = left/center/right. Needs tuning on
# a real board capture before the positioning advice is trustworthy.
BOARD_REGION = (0.20, 0.20, 0.80, 0.80)

_BOARD_PROMPT = """You are reading the player's OWN Teamfight Tactics board (the hex grid in the
center). For each champion currently ON the board (not the bench), report:
- name
- role: one of tank, bruiser, carry, caster, support (your best guess)
- row: front, mid, or back (front = closest to the enemy / top of the grid)
- side: left, center, or right

Return STRICT JSON: {"units": [{"name","role","row","side"}]}.
Only list units on the hex board. If unsure of a unit, still include it with your best guess."""


def read_board_pil(img: "Image.Image", model: str = "gpt-4o", crop=BOARD_REGION) -> dict:
    b64 = _b64(_crop_region(img, crop))
    resp = _client().chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": _BOARD_PROMPT},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}},
            ],
        }],
    )
    return json.loads(resp.choices[0].message.content)


def read_board(image_path: str, model: str = "gpt-4o", crop=BOARD_REGION) -> dict:
    return read_board_pil(Image.open(image_path).convert("RGB"), model, crop)


# ---- EXPERIMENTAL: read your chosen augments (for pivot weighing) -------------
# Your active augments show as 3 icons near your portrait / item bench. This reads
# them by name. Needs region tuning on a real capture.
AUGMENT_REGION = (0.0, 0.0, 0.18, 0.55)

_AUGMENT_PROMPT = """Read the player's ACTIVE AUGMENTS from this Teamfight Tactics screenshot crop
(the hexagonal augment icons, usually near the player's portrait / left side).
Return STRICT JSON: {"augments": ["<augment name>", ...]}.
List only augments you can identify; return an empty list if none are visible."""


def read_augments_pil(img: "Image.Image", model: str = "gpt-4o", crop=AUGMENT_REGION) -> dict:
    b64 = _b64(_crop_region(img, crop))
    resp = _client().chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": _AUGMENT_PROMPT},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}},
            ],
        }],
    )
    return json.loads(resp.choices[0].message.content)


def read_augments(image_path: str, model: str = "gpt-4o", crop=AUGMENT_REGION) -> dict:
    return read_augments_pil(Image.open(image_path).convert("RGB"), model, crop)


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()
    path = sys.argv[1] if len(sys.argv) > 1 else "fixtures/lobby_starups_3-3.png"
    data = read_lobby(path)
    print(json.dumps(data, indent=2))

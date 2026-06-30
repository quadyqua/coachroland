# Screen calibration — reading the TFT HUD

This file records how the live coach reads the screen, so the project can be **built and
verified on another machine without taking new screenshots.** A committed reference frame +
its expected reads stand in for a live game.

## Validated setup

- **Resolution:** 2560×1440 (16:9). Validated on a real Set 17 game.
- **Aspect ratio:** 16:9. All reader regions are stored as **fractions** of the screen
  (`(left, top, right, bottom)` in 0–1), so they are **resolution-independent within 16:9**
  — 1920×1080 and 2560×1440 both work unchanged. A different aspect ratio (21:9, 16:10) or a
  non-default in-game UI scale will shift elements and needs its own region pass.
- **Window mode:** Borderless (so OS screen capture / `mss` sees the game; exclusive
  fullscreen can capture black).

## What each region frames (the HUD layout)

| Region (fraction L,T,R,B) | Frames | Read by | Reliable? |
|---|---|---|---|
| `RIGHT_PANEL` (0.78, 0.08, 1.0, 0.97) | Right-side scoreboard: player names + HP + spiked unit | `read_lobby` (OCR) | Names/HP yes; star pips no |
| `SELF_REGION` (0.12, 0.80, 0.82, 1.0) | Bottom bar: 5 shop cards (name+cost), gold, level | `read_self` (OCR + roster) | Shop names yes; gold best-effort |
| `TRAIT_REGION` (0.0, 0.13, 0.135, 0.58) | Left trait panel: active trait names + counts | `read_traits` (OCR + trait list) | Yes (constrained to real traits) |
| `STAGE_REGION` (0.33, 0.0, 0.50, 0.055) | Top-center round indicator, e.g. "3-1" | `read_stage` (OCR + `N-N` regex) | Yes |
| `BENCH_REGION` (0.12, 0.655, 0.58, 0.745) | 9-slot bench row | `read_bench` (icon match) | **No** — see note |
| `ITEM_REGION` / `AUGMENT_REGION` / `OFFER_REGION` | Choice screens (items / augments / Gods) | icon match / OCR | Items+augments icon (WIP); Gods OCR yes |

**Reads are constrained to real data** so OCR can't hallucinate: champion names must match the
current-set roster (`cdragon.current_roster()`), trait names must match the set's trait list
(`cdragon.current_traits()`), and champion costs come from CDragon by name, not from OCR.

**Bench/board recognition does not work** by matching rendered tiles against flat CDragon art
(scores at noise). It needs a recognizer trained on **real frame crops** — that's why
`--save-frames` exists. Until then the bench feed is disabled and owned units are *inferred*
from shop diffs (`tracker.py`).

## Reference frame + expected reads

- **`fixtures/ref_1440p_planning.jpg`** — a real 2560×1440 Double Up planning-phase frame (stage 3-2).
- **`fixtures/ref_1440p_reads.json`** — the regions + the expected reader output on that frame.

## Verify on another machine (no live game needed)

```bash
pip install -r requirements.txt
# dump every region crop + every read from the committed frame:
python -m tftwatch.localvision calibrate fixtures/ref_1440p_planning.jpg
```

Open the `calib/*.png` crops — each should frame the thing in the table above — and compare the
printed reads against `fixtures/ref_1440p_reads.json`. If they match, your install reads the HUD
correctly. If a crop is off (different aspect ratio / UI scale), adjust that region's fraction in
`localvision.py` and re-run. The deterministic logic is covered separately by `tests/test_logic.py`.

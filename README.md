# TFTwatch

A **free, local** coaching tool for Teamfight Tactics. Two parts:

- **Coach Roland (live)** — reads your own screen and coaches you in real time on a
  second-monitor dashboard: what to buy, your comp direction, econ / level / roll
  timing, contest reads, item builds, and which God to pick. Double Up aware.
- **Scouting (Phase 0)** — point it at opponents via the Riot API and it predicts what
  each player will force this game, plus a lobby-wide "what's contested" read.

**Runs free by default.** The live coach uses local OCR + champion-icon matching and a
deterministic rules engine — no paid API needed, no keys required. An optional LLM
"brain" (`--brain`) can use OpenAI, but it's strictly opt-in.

## Safety / Riot policy

Coach Roland only **observes and suggests**. It reads your own screen and public data,
then advises in a separate window — it never automates input, never reads game memory,
and never draws an in-game overlay. The Riot-API scouting is fully read-only. Every
decision stays yours to make.

## Setup

```bash
cd TFTwatch
python -m venv .venv
.venv\Scripts\Activate.ps1         # PowerShell  (bash: source .venv/Scripts/activate)
pip install -r requirements.txt
```

No keys are needed for the **free live coach**. For scouting you need a Riot key, and
for the optional `--brain` an OpenAI key — put either in `.env` (`copy .env.example .env`).
A free Riot **Development** key (https://developer.riotgames.com) works; it expires every 24h.

## Live coach

```bash
# Free, local. Drag the window to your 2nd monitor -> http://127.0.0.1:8765
python -m tftwatch.dashboard --shop --offers --items --augments

# Double Up (pass your partner so it coaches the team, not contests it)
python -m tftwatch.dashboard --shop --offers --partner "Name#TAG" --partner-comp samira_reroll

# Preview the UI with no game running
python -m tftwatch.dashboard --demo
```

Flags: `--shop` (buy advice + pairs), `--offers` (God pick), `--items` (carry items),
`--augments`, `--partner` (Double Up), `--brain` (opt-in **paid** LLM reasoning),
`--board` (opt-in **paid** positioning), `--save-frames SECS` (capture frames for tuning).

## Scouting (Phase 0)

```bash
python -m tftwatch.cli scout "Faker#KR1" "Robinsongz#NA1"
python -m tftwatch.cli scout "Name#EUW" --matches 25 --platform euw1 --region europe
```

Gives, per opponent: rank, most-played comps (avg placement), and a next-game prediction;
plus the lobby-wide contested-lines read.

## What works vs. WIP (honest)

**Works, free, validated on real frames:**
- Scoreboard / contest detection, shop + costs, traits, **stage**, gold / level, God-choice pick.
- Free rules coach: comp direction from your board, **stage-aware** econ / level / roll timing,
  item theory (hold vs. slam, BIS components), shop-duplicate pair detection (with honest
  2-star math), and Double Up partner advice.

**Known gaps:**
- Reading **icon-only units** (your bench/board) and **item/augment icons** isn't reliable
  yet — matching rendered in-game tiles against flat CDragon assets scores at noise level.
  This needs a recognizer trained on real-frame crops; the bench feed is disabled so it can't
  give false advice in the meantime.
- Reader regions target **16:9** (1080p + 1440p validated); other layouts/UI scales may shift them.
- The LLM `--brain` needs OpenAI credits; the free rules coach is the default.

## Tests

```bash
python tests/test_logic.py        # fast, no vision/API — covers the core coach logic
```

## Notes

- Match data and Community Dragon data are cached under `.cache/`, so repeat runs are fast.
- Champion / item / trait names and costs come from Community Dragon (current set).

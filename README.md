# TFTwatch

Lobby scouting & comp prediction for Teamfight Tactics. **Phase 0** is live:
point it at your opponents and it tells you what each of them spams and what
they're most likely to force this game — plus a lobby-wide "what's contested"
read that the off-the-shelf apps don't synthesize for you.

All data comes from official, read-only Riot API endpoints. **No screen reading,
no input automation, no memory access → no Vanguard / ToS risk.**

## Setup

```bash
cd TFTwatch
python -m venv .venv
.venv\Scripts\activate            # Windows PowerShell:  .venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env            # then edit .env and paste your API key
```

Get a key at https://developer.riotgames.com (a free **Development** key works;
it expires every 24h — just regenerate it).

## Use

```bash
# Scout specific opponents (Name#TAG as shown in the client)
python -m tftwatch.cli scout "Faker#KR1" "Robinsongz#NA1"

# More history per player, different region
python -m tftwatch.cli scout "Name#EUW" --matches 25 --platform euw1 --region europe

# EXPERIMENTAL: auto-pull your current game's roster (only works mid-game)
python -m tftwatch.cli scout --from-lobby "You#NA1"
```

## What you get

- **Per opponent:** rank, their most-played comps (with avg placement), and a
  **prediction** of next game's comp + a signal (one-trick / strong preference /
  flex / leans).
- **Lobby read:** which lines are *contested* across the table — your cue to
  pivot off a crowded comp before you get starved of units.

## Roadmap

- **Phase 1** — hotkey screenshot + Claude vision to read an opponent's live
  board/bench/items on demand.
- **Phase 2** — reasoning engine: combine live boards + histories + meta into
  counter/positioning advice with a natural-language "why".
- **Phase 3** — overlay (Overwolf, Riot-allowlisted) for in-game display.

## Notes

- Match data is cached forever under `.cache/` (matches are immutable), so
  repeat runs are fast and stay under the dev-key rate limit.
- Champion/trait names are best-effort prettified from raw IDs; Phase 1 will map
  them through Community Dragon for exact display names.

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

## For an AI assistant (Claude Code) picking this up

If you're an AI assistant helping the user set this up or extend it on a new machine, read
this first, then walk them through **Part 1** below.

- **What it is:** a Python coaching tool for Teamfight Tactics. Two halves — a live "Coach
  Roland" that reads the user's *own* screen (mss capture + local RapidOCR) and coaches on a
  Flask dashboard, and an optional cloud "scout" API (the Docker/Kubernetes DevOps demo). The
  package is `tftwatch/`; tests are `tests/test_*.py` (run each with `python tests/<file>.py`,
  or all via `pytest`).
- **Hard rules (do not violate — these are the whole point):** it only *observes and suggests*.
  **Never** add input automation, memory reading, or an in-game overlay — TFT runs Vanguard
  anti-cheat and Riot's third-party policy forbids it. Opponent board/bench reading must stay
  **local (never sent to OpenAI)** and limited to what the user manually scouts — no reading all
  opponents at once ("omniscience" is the red line). See [POLICY.md](POLICY.md).
- **Run it free:** the default path needs no API keys (local OCR + a deterministic rules coach).
  OpenAI is opt-in (`--brain`); a Riot key is only for the pre-game `scout` CLI.
- **The `.env` file is gitignored — it does NOT come with the clone.** Recreate it from
  `.env.example` (or skip it entirely for local play).
- **First run downloads a ~25 MB CDragon data blob** (champion names/costs/traits) and caches it
  under `.cache/`; needs internet once. `cdragon.ensure_loaded()` guards the tests against a cold
  cache. On Windows, install `onnxruntime-directml` for a ~4× GPU speedup on the readers.
- **Try the logic with no game:** `python -m tftwatch.simulate --board "..." --shop "..." ...`
  runs the real coaching on a hypothetical spot — capture-free, no API. Good for verifying a
  working install and for exercising new coaching features.
- **Verify a checkout:** run `python tests/test_logic.py` (and the other `tests/test_*.py`);
  they should all report `N/N passed`.

## Getting started — from scratch

> **Heads-up:** the **Coach app you run to play needs only Python — no Docker, no
> Kubernetes.** Docker/Kubernetes is *only* for the separate, optional **Cloud Scout API**
> (a DevOps demo — see [k8s/README.md](k8s/README.md)). If you just want to use the coach,
> do **Part 1** and stop.
>
> **Platform:** the **live coach is Windows-only** — it screen-captures the running TFT game
> (Windows). On macOS/Linux you can still `pip install` and run the **tests + scenario
> simulator** (pure logic, no capture), just not the live screen reader.

### Part 1 — the Coach Roland app (what you run to play)

There are two ways to install. **Most people want the first one.**

#### Easiest — no coding, just double-click (Windows)

1. On this GitHub page, click the green **`< > Code`** button, then **Download ZIP**.
2. Find the downloaded ZIP (usually in **Downloads**), right-click it → **Extract All…** →
   put the folder somewhere easy like your **Desktop**.
3. Install **Python 3.12** from [python.org](https://www.python.org/downloads/). On the very
   first install screen, **tick the box "Add python.exe to PATH"** — this matters. Then finish.
4. Open the extracted folder and **double-click `setup.bat`**. It installs everything and
   downloads the champion data (a few minutes the first time). Wait until it says
   **"Setup complete"**, then close that window.
   - If Windows shows a blue **"Windows protected your PC"** box, click **More info → Run anyway**
     (that appears for any downloaded script — it's expected).
5. In TFT, set **Settings → Video → Window Mode → Borderless**.
6. **Double-click `run.bat`** whenever you want to play. A browser tab opens with the coach —
   then start your TFT game. To stop, just close the black window.

That's the whole thing — two double-clicks after Python is installed.

#### Manual — the terminal way (Windows/macOS/Linux)

**1. Install the prerequisites (Windows 10/11):**
- **Python 3.12+** — from [python.org](https://www.python.org/downloads/). On the first
  installer screen, tick **"Add python.exe to PATH"**. Verify in a new terminal: `python --version`.
- **Git** — from [git-scm.com](https://git-scm.com/download/win). Verify: `git --version`.

**2. Get the code and install dependencies:**
```powershell
git clone https://github.com/quadyqua/coachroland.git
cd coachroland
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # PowerShell   (Git Bash: source .venv/Scripts/activate)
pip install -r requirements.txt
```
> If `Activate.ps1` errors with *"running scripts is disabled on this system,"* PowerShell is
> blocking local scripts (common on a fresh machine). Run once:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then re-run the activate line — or
> just use Git Bash (`source .venv/Scripts/activate`), which has no such restriction.
> The `pip install` pulls `rapidocr-onnxruntime` (OCR) and its deps, so it can take a minute.

**3. (Optional) GPU acceleration** — any DirectX 12 GPU (NVIDIA/AMD/Intel) makes the screen
readers ~4× faster. The app auto-detects it and falls back to CPU if absent:
```powershell
pip uninstall -y onnxruntime
pip install onnxruntime-directml
```

**4. (Optional) API keys** — the **live coach needs no keys**. You only need them for:
- **Scouting / post-game review** → a Riot key: grab a free **Development** key at
  [developer.riotgames.com](https://developer.riotgames.com) (expires every 24h).
- **`--brain`** (LLM reasoning) → an OpenAI key.

  Put either in a `.env` file: `copy .env.example .env`, then edit it. Note the `.env` is
  **gitignored**, so it does **not** come with the clone — recreate it here (or skip it for
  local play).

**5. One game setting:** in TFT, set **Settings → Video → Window Mode → Borderless**. The
reader can't capture a true-fullscreen game.

**6. Run it:**
```powershell
python -m tftwatch.dashboard --shop --offers --items --augments
```
Open **http://127.0.0.1:8765** in a browser and drag it to your second monitor. Just play —
it reads your screen and coaches on its own. Preview the UI with no game via `--demo`.
The **first run downloads a ~25 MB champion-data file** (cached under `.cache/`, so it's a
one-time wait) — you need an internet connection that first time.

**7. Verify the install** (no game needed — runs the reader/logic tests):
```powershell
python tests/test_logic.py
```

### Part 2 — the Cloud Scout API (optional; this is the Docker + Kubernetes part)

A containerized version of the scout, deployed to Kubernetes. **Not needed to use the coach.**
Full from-scratch steps — installing **WSL2**, **Docker Desktop**, enabling **Kubernetes**, then
build + deploy — are in **[k8s/README.md](k8s/README.md)**.

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

## Try it without a game — scenario simulator

Ask Roland what to do for any hypothetical board + shop — **no live game, screen capture, or
API needed.** Great for learning the coaching or sanity-checking a spot:

```powershell
python -m tftwatch.simulate --board "Caitlyn,Briar,Rek'Sai" --shop "Meeple,Teemo,Caitlyn,Rek'Sai,Briar" --gold 20 --stage 2-7 --level 5
```

It prints your active traits, the comp it commits to, per-slot shop advice (**buy / deny / skip**),
econ, and the coach's calls. Add `--comp <key>` to pin a comp, `--contested "X,Y"` to flag
lobby-contested carries (deny advice), or `--level/--gold/--stage` for accurate pacing.

## Scouting (Phase 0)

```bash
python -m tftwatch.cli scout "Faker#KR1" "Robinsongz#NA1"
python -m tftwatch.cli scout "Name#EUW" --matches 25 --platform euw1 --region europe
```

Gives, per opponent: rank, most-played comps (avg placement), and a next-game prediction;
plus the lobby-wide contested-lines read.

## Cloud scout service (Docker + Kubernetes)

The scout also runs as a **containerized HTTP service on Kubernetes** — the "cloud brain"
half of the project (public Riot data only, no screen reading), split out from the desktop
client so it can run as a stateless, scalable service.

```
browser → Ingress (scout.localhost) → Service → scout pods ×2 → Postgres + PersistentVolume
```

- **FastAPI** service (`tftwatch/api.py`) — `GET /scout?riot_id=Name%23TAG`, plus `/healthz` and auto-docs at `/docs`
- **Postgres** match cache (`tftwatch/cache.py`) — immutable match data cached across pod restarts (~7.5× faster on a cache hit)
- **Kubernetes** (`k8s/`) — Deployment (2 self-healing replicas), Service, Secrets, ConfigMap, PersistentVolumeClaim, and nginx Ingress

```bash
docker build -t tftwatch-scout:v2 .
kubectl create secret generic riot-api      --from-literal=RIOT_API_KEY="RGAPI-..."
kubectl create secret generic postgres-auth --from-literal=POSTGRES_PASSWORD="devpassword"
kubectl apply -f k8s/          # → http://scout.localhost/docs
```

**Full architecture, walkthrough, and design decisions: [k8s/README.md](k8s/README.md).**

## Post-game review

```bash
python -m tftwatch.review "Name#TAG"      # break down your last game
```

Pulls your most recent match from the Riot API and reviews it for learning: placement,
your carry + items (vs. BIS), comp match, traits, augments, level. This is where
stat-heavy analysis lives — Riot's TFT policy keeps win-rates/placements out of *live*
play, but post-game is fine. Needs a Riot key in `.env`.

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

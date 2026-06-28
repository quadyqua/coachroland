# Riot compliance — bright lines for TFTwatch

TFTwatch is a **personal, observe-only** coaching tool. This file records the rules we
hold ourselves to so the project stays on the right side of Riot's policy and anti-cheat
as it grows. It's our read of Riot's published policy — not legal advice, and not endorsed
by Riot Games.

## Allowed (what we do)
- **Read the player's own screen** via normal OS screen capture (same mechanism as OBS /
  screenshots). This does not touch the game process or memory, so it isn't what Vanguard
  targets.
- **Riot's public, read-only API** for pre-game opponent scouting (officially sanctioned).
- **Qualitative live advice** that the player could reason out themselves — buy/comp/econ/
  level/roll/item/God suggestions in a **separate window** on a second monitor.
- **Stat-heavy analysis post-game** (review, learning), where live-display rules don't apply.

## Never add (instant bright-line violations)
- ❌ **Input automation / scripting / botting** — any simulated clicks or keypresses to the game.
- ❌ **Reading game memory, DLL injection, or any process tampering** — this is what Vanguard bans.
- ❌ **An in-game overlay** that draws on or interacts with the Riot client. Advice lives in a
  separate window only.
- ❌ **Surfacing information the player couldn't see** — opponent benches, hidden info, etc.
- ❌ **Live augment / legend (God) win-rates or augment average placements.** Riot's TFT
  third-party policy explicitly prohibits *displaying* these during play. Keep live picks
  qualitative ("strong this patch", "best of the three"); put any win-rate/placement numbers
  in **post-game** review only.

## If it were ever distributed (not just personal)
- Public third-party apps need Riot (and platform) approval, must offer a free version, and must
  carry a "not endorsed by Riot Games" disclaimer. Until then: **personal use only.**

## Sources
- Riot — Third-Party Applications: https://support.riotgames.com/en-us/riot/events/third-party-applications
- Riot — Vanguard FAQ for Third-Party Applications: https://www.riotgames.com/en/DevRel/vanguard-faq
- Overwolf — Riot Games compliance guide: https://dev.overwolf.com/ow-native/guides/game-compliance/riot-games/

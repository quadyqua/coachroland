# How Coach Roland decides

Plain-English walkthrough of the live decision logic, so the advice is never a black box.

## Picking your comp (from your traits)

1. **Read your trait panel** (left side) — the active traits come from units **on your
   board** only; bench units don't count.
2. **Only commit at a breakpoint.** A comp is chosen only when one of your traits is at
   **2+**. With everything at 1 (e.g. turn-1 PvP) it commits to **nothing** and keeps you
   flexible — this is what stops it flipping to a random comp off a single stray unit.
3. **Match the defining trait.** When a trait hits 2+, it picks the meta comp whose
   *first-listed* (defining) trait is your strongest active trait — uncontested, best tier.
4. **Stickiness.** Once committed it holds that comp while its defining trait stays within 1
   of your strongest — so a noisy combat/transition frame can't yank you off your line.

## What it tells you to buy

Each shop unit is tagged by its **role** (from the champion's real CDragon traits):
- **your carry** — buy every copy you can.
- **comp core** — shares your comp's defining trait.
- **frontline body** — in the comp's board but off-trait (e.g. Pantheon in Space Groove).
- **pair** — you hold 2+ copies *and* it's in your comp → collect toward a 2★.

Off-comp units are never flagged. The carry's star target is realistic: chase a 3★ ("gold")
only for low-cost reroll carries; for 4-5 cost / fast-8-9 carries, buy toward 2★ and to deny.

## Board progress (without reading 3D models)

It estimates which of your comp's board units you already field from **trait counts**: if a
trait is active at ≥ the number of your comp's units carrying it, you clearly have them — so
they're credited even if the shop-diff buy-tracker missed them.

## Timed picks (Gods / augments)

- **God**: prefers a God that fits your playstyle, then lower variance (reliable), then patch
  preference. Pinned to the top with a ~30s countdown.
- **Augment**: an emblem that points your comp > a proven strong augment > econ early /
  combat late. Live win-rates are intentionally not shown (Riot TFT policy — see `POLICY.md`);
  stat-heavy analysis lives in post-game `review.py`.

## What it never does

Observe-and-suggest only: no input automation, no memory reads, no in-game overlay, no hidden
information. Every call stays yours to make.

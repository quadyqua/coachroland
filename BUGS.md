# Bug log — found by comparing live reads vs. the real screen

Running log of issues caught while play-testing the live coach against real games
(method: capture a frame with `mss`, run every reader, diff against the actual screen
and the dashboard `/state`). Newest first.

## Fixed

- **Cold-cache test flake (false green).** On a fresh cache/clone/set-rotation the 25 MB CDragon
  blob downloads mid-run, so cost/trait lookups returned empty for the first calls and the suite
  reported a misleading partial pass (e.g. 18/20) that only went green once the cache warmed — so
  "locked by tests" wasn't trustworthy right after a cache wipe. Now `cdragon.ensure_loaded()`
  forces the data up front and raises loudly if it's genuinely unavailable; called from
  `tests/conftest.py` (pytest) and each standalone runner's `__main__`. Also `champ_traits()` now
  returns a copy, not its internal cached list (removes a latent cache-poisoning trap).
- **Comp database validated against CDragon.** A full audit of all 26 comps found and fixed
  15 with issues: invented traits (Summon/Invoker/Sorcerer/Sentinel/Summoner/Mystic), wrong
  item names (Leviathan→Nashor's Tooth, Madred's Bloodrazor→Giant Slayer, Power Gauntlet,
  Runaan's), and boards that couldn't field their own trait. Now 0 issues, locked by
  `test_comp_traits_and_items_are_real` + `test_comp_boards_have_real_units`.
- **Advice contradicted the comp panel.** On a combat / transition / choice-screen frame
  the trait read is empty, so the rules path fell back to "no comp → suggest open lines"
  while the committed comp was still shown — telling you to switch off your own line. Now
  the advice keeps using your committed comp when traits aren't readable that frame.
- **Comp flipped on noisy frames** (Ez Cho / LeBlanc): a single stray count-1 trait could
  re-pick the comp. Now only traits at a real breakpoint (2+) drive a pick, plus stickiness.
- **Item advice for the wrong carry** (Recurve Bow → Guinsoo's on LeBlanc while on Space
  Groove): same comp-flicker root; fixed by the breakpoint + stickiness rules.
- **Off-comp pair buys** (told to buy Lissandra on Space Groove): pairs are only chased if
  in your comp now.
- **"Open lines" nagging** when committed + uncontested: suppressed.
- **Carry star-target unrealistic** (implying you 3-star a 4-cost Nami): now states the real
  target by cost (reroll = chase 3-star; fast-8/9 = play 1-2 star with items).
- **Trait read picked up junk** ("NaeNae", player names): constrained to real CDragon traits.
- **Level pacing** said "level to 9 at 1-4": stage 1 is auto-leveled; skip it.
- **HP misreads** firing false "about to die": plausibility guard rejects impossible crashes.
- **Alt-tab blanked everything**: a brief tab-out tripped game-over + reset. Now time-gated
  (45s) so quick tab-outs keep your comp/advice.
- **Buys looked arbitrary** (why buy Pantheon?): each buy now says its role — your carry /
  comp core (shares your trait) / frontline body.

## Known / open

- **Reader misses on combat & choice frames** — during a fight or a special screen, the
  scoreboard/shop/traits aren't fully visible, so the lobby read can return < 8 players,
  the shop < 5 slots, and traits empty. Expected; the advice now holds the committed comp
  through these frames so it doesn't thrash.
- **Special choice screens read as "shop"** — e.g. "Penge's Parting Gift" (pick a free
  champion) gets read by the bottom-bar reader as the shop. Needs detection of these
  one-off screens so they aren't treated as the normal shop.
- **Bench/board unit recognition** — still unreliable from CDragon icons; owned units are
  inferred from shop diffs. Needs a recognizer trained on real frame crops (`--save-frames`).
- **God / augment choice readers** — built but not yet validated against a real captured
  frame of those (transient screens; capture-timing is the blocker).
- **Artifact Anvil not advised.** Standard completed items are covered, and a *radiant* of a
  BIS item is caught + flagged `radiant` (a strict upgrade). But the Artifact-Anvil pool
  (Titanic Hydra, Void Gauntlet, Blighting Jewel, … — 74 items) has no reader or "which
  artifact for this carry" knowledge base. Needs both (the reader wants one live anvil frame).
  Item-emblems similar (augment-emblems are already weighted in `choose_augment`).
- **Deep comp accuracy (win-rates / exact splash units)** — comp tiers and the exact
  optimal splash units still come from a hand-curated snapshot, not live stats. The
  structure (carry, traits, board, items) is now CDragon-validated (see below), but the
  *meta ranking* refreshes per patch and ideally auto-pulls from a stats API later.

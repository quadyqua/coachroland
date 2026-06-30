# Bug log — found by comparing live reads vs. the real screen

Running log of issues caught while play-testing the live coach against real games
(method: capture a frame with `mss`, run every reader, diff against the actual screen
and the dashboard `/state`). Newest first.

## Fixed

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
- **Some comp final-boards are inaccurate** — a CDragon audit (`_audit`-style, now guarded by
  `test_comp_boards_have_real_units`) found a few boards short on their own defining trait
  (`mecha_sol` 1 Mecha, `viktor_nami` 0 Primordian, `challenger_mf` 1 Challenger) from the
  noisy source parse. Low impact: the comp *grounding* matches on the claimed trait, not the
  board, so the right comp is still picked — but the displayed board + buy roles for those few
  comps are off. Needs re-verification against a clean meta source (Mobalytics blocks scraping;
  TFTAcademy parses noisily). Fixed so far: removed a stray "Relic" from `nova_vex`.

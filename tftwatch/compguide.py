"""Comp + counter knowledge base — Set 17 (patch 17.6) snapshot.

Hand-curated from public guides (bunnymuffins / tftacademy / mobalytics / metasrc /
metabot, patch 17.6). Two honest caveats baked into how this is written:
  1. Win-rates shift every patch and Double Up samples are noisy, so this stores
     TIER + playstyle + qualitative counters, not precise win % (refresh per patch;
     ideally auto-pull from a stats API later).
  2. TFT has no "comp A beats comp B" matrix. Counters are POSITIONAL + ITEM + TEMPO,
     stored as COUNTER_DYNAMICS below.

Using public comp guides for your own play is in the allowed zone (no hidden info).
"""

# playstyle: "fast9" (weak early, scales to legendaries) | "reroll" (strong now, caps low)
#            | "flex" (adapts)
# double_up: short note on team fit (frontline anchor vs backline carry, reinforce value)
COMPS = {
    "vex_fast9": {
        "name": "Vex Fast 9", "carry": "Vex", "playstyle": "fast9", "tier": "S",
        "double_up": "Strong, but you're weak until 8-9 — lean on your partner to cover early.",
        "counters": ["Weak early — punish before they hit 9", "Reposition vs assassins"],
        "source": "bunnymuffins (17.6)"},
    "jhin_fast9": {
        "name": "Jhin Fast 9", "carry": "Jhin", "carry_cost": 4, "playstyle": "fast9", "tier": "A",
        "carry_items": ["Red Buff", "Striker's Flail", "Last Whisper"],
        "carry_components": ["Recurve Bow", "B.F. Sword", "Sparring Gloves"],
        "early_units": ["Caitlyn", "Talon", "Aatrox", "Jax"],
        "early_alt": ["Timebreaker opener", "Graves", "Vex", "Sona", "Fiora"],
        "flexible_components": ["B.F. Sword", "Recurve Bow"],
        "level_plan": "Stage 2 win-streak (slam items), econ to fast 8, roll for Jhin at 8-9.",
        "double_up": "Backline carry — pair with a frontline partner; reinforce them once you win.",
        "counters": ["Squishy backline — gets dived; corner Jhin", "Weak early"],
        "source": "metasrc / tftacademy (17.6)"},
    "mecha": {
        "name": "Mecha", "carry": "flex", "playstyle": "flex", "tier": "A",
        "double_up": "Transform tempo spikes — good reinforce value.",
        "counters": ["Sustained true/magic damage through the transform"],
        "source": "bunnymuffins (17.6)"},
    "samira_reroll": {
        "name": "Two Tanky Samira Reroll", "carry": "Samira", "playstyle": "reroll", "tier": "A",
        "double_up": "Strong NOW, caps low — win early or you fade late vs fast-9 teams.",
        "counters": ["Out-scaled late by legendaries", "Bramble/Steadfast vs her bursts"],
        "source": "bunnymuffins (17.6)"},
    "brawler_yi": {
        "name": "Brawler Yi", "carry": "Master Yi", "playstyle": "reroll", "tier": "A",
        "double_up": "Yi dives backlines — pair with a tanky partner.",
        "counters": ["CC (stun/chill) shuts Yi down", "Bramble vs crit", "Corner to bait him"],
        "source": "bunnymuffins (17.6)"},
    "primordian_jinx": {
        "name": "Primordian Jinx", "carry": "Jinx", "playstyle": "flex", "tier": "A",
        "double_up": "Backline hyper-carry — needs frontline cover from partner.",
        "counters": ["Dive her backline before she ramps", "Corner her"],
        "source": "bunnymuffins (17.6)"},
    "lissandra_reroll": {
        "name": "Lissandra Reroll", "carry": "Lissandra", "playstyle": "reroll", "tier": "A",
        "double_up": "AP reroll, strong mid — win the tempo window.",
        "counters": ["MR items / out-scale late"],
        "source": "bunnymuffins (17.6)"},
    "meeple_veigar": {
        "name": "Meeple Veigar", "carry": "Veigar", "playstyle": "reroll", "tier": "A",
        "double_up": "AP reroll — caps low, push your early advantage.",
        "counters": ["MR / Dodge", "Out-scaled late"],
        "source": "bunnymuffins (17.6)"},
    "vanguard_fast9": {
        "name": "Vanguard Fast 9", "carry": "flex", "playstyle": "fast9", "tier": "A",
        "double_up": "Heavy frontline — great as the team's anchor; partner brings damage.",
        "counters": ["Armor pen / magic / sustained DPS chews the frontline", "Weak early"],
        "source": "bunnymuffins (17.6)"},
    "darkstar_sniper": {
        "name": "Dark Star Sniper", "carry": "Sniper", "playstyle": "flex", "tier": "A (Double Up)",
        "double_up": "Top Double Up pick by data — long-range backline carry; partner frontlines.",
        "counters": ["Dive / gap-close to the snipers", "Corner protects them"],
        "source": "metasrc Double Up (17.5)"},
    "nova_challenger": {
        "name": "N.O.V.A. Challenger", "carry": "flex", "playstyle": "flex", "tier": "A (Double Up)",
        "double_up": "Strong Double Up — fast attackers, good reinforce value.",
        "counters": ["CC + frontline to absorb the dive"],
        "source": "metasrc Double Up (17.5)"},
    "heatdeath_morde": {
        "name": "Heat Death Mordekaiser", "carry": "Mordekaiser", "carry_cost": 2,
        "playstyle": "reroll", "tier": "B",
        "carry_items": ["Void Staff", "Morellonomicon", "Jeweled Gauntlet"],
        "carry_components": ["Needlessly Large Rod", "Tear", "Sparring Gloves"],
        "early_units": ["Mordekaiser", "Leona"], "early_alt": ["Primordian opener", "Timebreaker"],
        "flexible_components": ["Needlessly Large Rod", "Tear"],
        "level_plan": "Level 4/5/6 on upgrades, slow-roll at 6 to 2-star Morde + a tank.",
        "double_up": "Bruiser frontline-carry — a solid anchor for a backline partner.",
        "counters": ["Magic resist / anti-heal (Morello mirror)", "Out-scaled late"],
        "source": "tftflow / mobalytics (17.6)"},
}

# Real counter DYNAMICS (positional + item + tempo) — what actually "counters" things.
COUNTER_DYNAMICS = {
    "assassins": "Corner your carry (force them to jump the front), or bait with a bottom-right "
                 "tank. Bramble Vest negates their crit; CC/Enchanters shut them down.",
    "heavy_frontline": "You need armor penetration, magic damage, or sustained DPS to chew through "
                       "— burst alone bounces off. Last Whisper / Void Staff / Giant Slayer.",
    "backline_carry": "Gap-close or dive it (assassins/divers), or it melts you from range. If you "
                      "can't reach it, out-tank the fight.",
    "fast9": "They're weak until level 8-9 — punish them early. A strong stage 2-3 board makes them "
             "lose HP before their legendaries come online.",
    "reroll": "They cap lower — they're strongest NOW and fade late. Don't fight them even; stall, "
              "stay healthy, and out-scale them with a fast-9 line if the game goes long.",
}

# Double Up team-construction principles (always team-aware).
DOUBLE_UP_NOTES = [
    "One partner anchors frontline, the other carries backline — so reinforcements complete a board.",
    "Never both force the same carry (shared pool starves you both).",
    "You only fight one enemy team's board each round + reinforcements — counter what you actually face.",
]


# Set 17 "Realm of the Gods" — 2 of these 9 are offered per game; you pick offerings.
GODS = {
    "Ahri": {"gives": "gold, XP, rerolls", "best_for": "fast8/9", "variance": "low",
             "note": "Econ engine — great for fast-9; prioritize item augments alongside."},
    "Soraka": {"gives": "2 HP per missing Tactician HP", "best_for": "fast9", "variance": "low",
               "note": "Best when low / playing a comeback into fast 9."},
    "Kayle": {"gives": "items", "best_for": "any", "variance": "low",
              "note": "Reliable item value — safest low-variance pick."},
    "Ekko": {"gives": "artifacts on a timer", "best_for": "win-streak", "variance": "mid",
             "note": "Strong but patient — take it if you're ahead / streaking."},
    "Aurelion Sol": {"gives": "quest rewards", "best_for": "flex", "variance": "high",
                     "note": "Big swings via quests — high-roll upside."},
    "Evelynn": {"gives": "high-risk rewards", "best_for": "flex", "variance": "high",
                "note": "Biggest upside, biggest risk."},
    "Thresh": {"gives": "random boons", "best_for": "gamble", "variance": "high",
               "note": "Everything random — only if you embrace variance."},
    "Varus": {"gives": "see current patch", "best_for": "flex", "variance": "mid",
              "note": "Offerings vary by patch — check before committing."},
    "Yasuo": {"gives": "see current patch", "best_for": "flex", "variance": "mid",
              "note": "Offerings vary by patch — check before committing."},
}

# Top Set 17 augments (17.6) — exact ranking needs live augment-stat data.
TOP_AUGMENTS = {"Advanced Loan", "Aura Farming", "Cosmic Restart", "Epoch+", "Explosive Growth"}


def find(carry_or_key: str):
    """Look up a comp by key or by carry name (case-insensitive)."""
    if not carry_or_key:
        return None
    k = carry_or_key.lower()
    if k in COMPS:
        return COMPS[k]
    for comp in COMPS.values():
        if comp.get("carry", "").lower() == k:
            return comp
    return None


def open_comps(contested_carries):
    """Comps whose carry is NOT being contested — the 'never assume, read the lobby' filter."""
    contested = {c.lower() for c in (contested_carries or [])}
    tier_rank = {"S": 0, "A": 1, "A (Double Up)": 1, "B": 2, "C": 3}
    out = [c for c in COMPS.values() if c.get("carry", "").lower() not in contested]
    return sorted(out, key=lambda c: tier_rank.get(c.get("tier"), 9))

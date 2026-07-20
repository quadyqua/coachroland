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
# `traits`: the trait(s) that DEFINE the comp — used to match your live trait read to the
# right comp. `final_board`: the level 8-9 board. Curated from tftacademy (Set 17, patch 17.6).
COMPS = {
    "dark_star_jhin": {
        "name": "Dark Star Flex (Jhin)", "carry": "Jhin", "playstyle": "fast9", "tier": "S",
        "traits": ["Dark Star", "Sniper"],
        "carry_items": ["Last Whisper", "Deathblade", "Infinity Edge"],
        "early_units": ["Kai'Sa", "Karma", "Cho'Gath"],
        "final_board": ["Tahm Kench", "Cho'Gath", "Nunu", "Mordekaiser", "Galio", "Bard", "Karma", "Kai'Sa", "Jhin"],
        "level_plan": "Aim for 6 Dark Star. Win-streak stage 2, push to 8 then 9 — Jhin is the cap, Kai'Sa secondary.",
        "double_up": "Backline carry — pair with a frontline partner; the cleanest S-tier pick.",
        "counters": ["Dive the squishy backline", "Corner Jhin"],
        "source": "tftacademy (17.6)"},
    "stargazer_xayah": {
        "name": "Xayah Stargazer", "carry": "Xayah", "playstyle": "fast8", "tier": "S",
        "traits": ["Stargazer", "Vanguard", "Bastion"],
        "carry_items": ["Runaan's Untamed Hurricane", "Runaan's Untamed Hurricane", "Rapid Firecannon"],
        "early_units": ["Samira", "Aatrox", "Jax"],
        "final_board": ["Aatrox", "Jax", "Maokai", "Rhaast", "Nunu", "Tahm Kench", "Xayah", "Jhin"],
        "level_plan": "Samira as temp carry early. Level to 8, roll for Xayah 2 + upgraded frontline.",
        "double_up": "Backline carry behind a Vanguard/Bastion wall — partner can frontline.",
        "counters": ["Gap-close to Xayah", "Sustained frontline"],
        "source": "tftacademy (17.6)"},
    "nova_vex": {
        "name": "N.O.V.A. Vex (9-5)", "carry": "Vex", "playstyle": "fast9", "tier": "A",
        "traits": ["N.O.V.A.", "Vanguard"],
        "carry_items": ["Guinsoo's Rageblade", "Rabadon's Deathcap", "Rapid Firecannon"],
        "early_units": ["Graves", "Akali", "Fiora"],
        "final_board": ["Aatrox", "Akali", "Rhaast", "Nunu", "Shen", "Blitzcrank", "Fiora", "Graves", "Vex"],
        "level_plan": "AD win-streak opener (Graves/Vex items). Push level 9 by stage 4, stay above 80 HP.",
        "double_up": "Backline carry — strong N.O.V.A. frontline lets your partner go damage.",
        "counters": ["Weak early — punish before 9", "Reposition vs assassins"],
        "source": "tftacademy (17.6)"},
    "space_groove": {
        "name": "Space Groove (In The Groove)", "carry": "Nami", "playstyle": "fast8", "tier": "B",
        "traits": ["Space Groove"],
        "carry_items": ["Nashor's Tooth", "Jeweled Gauntlet", "Giant's Belt"],
        "early_units": ["Nami", "Riven", "Nunu", "Blitzcrank"],
        "final_board": ["Gwen", "Pantheon", "Ornn", "Nunu", "Tahm Kench", "Nami", "Riven", "Shen", "Blitzcrank"],
        "level_plan": "Get 5 Space Groove active. Fast 8, play around Nami / Riven / Nunu / Blitzcrank.",
        "double_up": "Frontline-heavy AP line — solid team anchor.",
        "counters": ["Burst the backline before it ramps"],
        "source": "tftacademy (17.6)"},
    "mecha_sol": {
        "name": "Mecha Aurelion Sol", "carry": "Aurelion Sol", "playstyle": "fast8", "tier": "A",
        "traits": ["Mecha", "Brawler", "Voyager"],
        "carry_items": ["Rabadon's Deathcap", "Statikk Shiv", "Jeweled Gauntlet"],
        "early_units": ["Aurelion Sol", "Urgot", "Morgana"],
        "final_board": ["Aurelion Sol", "Urgot", "The Mighty Mech", "Karma", "Rhaast", "Mordekaiser", "Morgana", "Blitzcrank"],
        "level_plan": "Loss-streak stage 2 for items. Level 6/7 standard, then 8 and roll hard for 2-star Mecha.",
        "double_up": "Transform tempo spikes — good reinforce value as a flex anchor.",
        "counters": ["Sustained true/magic damage through the transform"],
        "source": "tftacademy (17.6)"},
    "samira_reroll": {
        "name": "Two Tanky Samira Reroll", "carry": "Samira", "playstyle": "reroll", "tier": "A",
        "traits": ["Sniper", "Space Groove"],
        "carry_items": ["Spear of Shojin", "Deathblade", "Last Whisper"],
        "early_units": ["Samira", "Ornn", "Nasus"],
        "final_board": ["Nasus", "Ornn", "Samira", "Nami", "Blitzcrank", "Jhin"],
        "level_plan": "Needs the Two Tanky augment. Slow-roll stage 4 for 3-star Samira behind Ornn + Nasus.",
        "double_up": "Strong NOW, caps low — win early or fade vs fast-9 teams.",
        "counters": ["Out-scaled late by legendaries", "Bramble/Steadfast vs her bursts"],
        "source": "tftacademy (17.6)"},
    "yi_marauder": {
        "name": "Yi Marawlers (Master Yi)", "carry": "Master Yi", "playstyle": "fast8", "tier": "A",
        "traits": ["Marauder", "Brawler", "Psionic", "N.O.V.A.", "Challenger"],
        "carry_items": ["Guardian Angel", "Giant Slayer", "Guinsoo's Rageblade"],
        "early_units": ["Master Yi", "Gragas", "Urgot"],
        "final_board": ["Master Yi", "Kindred", "Tahm Kench", "Maokai", "Gragas", "Fiora", "Bel'Veth", "Urgot"],
        "level_plan": "4-cost Fast 8. Level 8 at natural intervals, roll for Master Yi 2 with upgraded Brawlers.",
        "double_up": "Yi dives backlines — pair with a tanky partner.",
        "counters": ["CC (stun/chill) shuts Yi down", "Bramble vs crit", "Corner to bait him"],
        "source": "tftacademy (17.6)"},
    "primordian_jinx": {
        "name": "Primordian Jinx", "carry": "Jinx", "playstyle": "reroll", "tier": "A",
        "traits": ["Primordian", "Challenger", "Marauder"],
        "carry_items": ["Rapid Firecannon", "Deathblade", "Last Whisper"],
        "early_units": ["Rek'Sai", "Bel'Veth", "Akali"],
        "final_board": ["Briar", "Akali", "Bel'Veth", "Jinx", "Maokai", "Rhaast", "Kindred", "Rek'Sai"],
        "level_plan": "Win-streak Primordian early. Slow-roll above 50g for 3-star Jinx; add Kindred at 7, Rhaast at 8.",
        "double_up": "Backline hyper-carry — needs frontline cover from partner.",
        "counters": ["Dive her backline before she ramps", "Corner her"],
        "source": "tftacademy (17.6)"},
    "primordian_reroll": {
        "name": "Primordian Briar (Reroll)", "carry": "Briar", "playstyle": "reroll", "tier": "B",
        "traits": ["Primordian", "Rogue"],
        "carry_items": ["Sterak's Gage", "Titan's Resolve", "Bloodthirster"],
        "early_units": ["Cho'Gath", "Rek'Sai", "Bel'Veth"],
        "final_board": ["Cho'Gath", "Briar", "Rek'Sai", "Bel'Veth", "Kindred", "Kai'Sa", "Akali", "Rhaast", "Jhin"],
        "level_plan": "Beginner-friendly. Field 3 Primordians stage 2, slow-roll stage 3-4 for 3-stars, cap at 9 with Jhin.",
        "double_up": "Bruiser frontline-carry — a forgiving anchor for a backline partner.",
        "counters": ["Out-scaled late", "Anti-heal vs Briar"],
        "source": "tftacademy (17.6)"},
    "veigar_printer": {
        "name": "Veigar Printer (Meeple)", "carry": "Veigar", "playstyle": "reroll", "tier": "A",
        "traits": ["Meeple", "Bastion", "Dark Star"],
        "carry_items": ["Nashor's Tooth", "Nashor's Tooth", "Jeweled Gauntlet"],
        "early_units": ["Veigar", "Poppy", "Lissandra"],
        "final_board": ["Veigar", "Poppy", "Lissandra", "Ivern Minion", "Mordekaiser", "Illaoi", "Rammus", "Bard"],
        "level_plan": "AP win-streak with Veigar 2 stage 2. Slow-roll above 50g for 3-star Veigar/Poppy/Lissandra.",
        "double_up": "AP reroll — caps low, push your early advantage.",
        "counters": ["MR / Dodge", "Out-scaled late"],
        "source": "tftacademy (17.6)"},
    "darkstar_lissandra": {
        "name": "Dark Star Lissandra", "carry": "Lissandra", "playstyle": "reroll", "tier": "A",
        "traits": ["Dark Star", "Anima", "Vanguard"],
        "carry_items": ["Jeweled Gauntlet", "Nashor's Tooth", "Nashor's Tooth"],
        "early_units": ["Lissandra", "Cho'Gath"],
        "final_board": ["Lissandra", "Cho'Gath", "Ezreal", "Mordekaiser", "Pantheon", "Kai'Sa", "Karma", "Galio", "Jhin"],
        "level_plan": "Win-streak with Lissandra 2 + AP items stage 2. Slow-roll above 50g for Lissandra/Cho 3, aim 6 Dark Star.",
        "double_up": "AP frontline-carry — strong mid, win the tempo window.",
        "counters": ["MR items / out-scale late"],
        "source": "tftacademy (17.6)"},
    "vanguard_zoe": {
        "name": "Vanguard Zoe", "carry": "Zoe", "playstyle": "reroll", "tier": "C",
        "traits": ["Vanguard", "Shepherd"],
        "carry_items": ["Jeweled Gauntlet", "Crownguard", "Rabadon's Deathcap"],
        "early_units": ["Zoe", "Leona", "Mordekaiser"],
        "final_board": ["Zoe", "Leona", "Mordekaiser", "Illaoi", "Leblanc", "Karma", "Nunu", "Bard"],
        "level_plan": "Win-streak Zoe/Leona stage 2. Level 6 and roll for 4 Vanguard + 3 Shepherd, 3-star Leona.",
        "double_up": "Heavy frontline anchor — partner brings the damage.",
        "counters": ["Armor pen / sustained DPS chews the frontline"],
        "source": "tftacademy (17.6)"},
    "shepherd_pie": {
        "name": "Shepherd Pie (LeBlanc)", "carry": "LeBlanc", "playstyle": "fast8", "tier": "A",
        "traits": ["Shepherd", "Vanguard"],
        "carry_items": ["Guinsoo's Rageblade", "Giant Slayer", "Archangel's Staff"],
        "early_units": ["LeBlanc", "Karma", "Lissandra"],
        "final_board": ["LeBlanc", "Karma", "Lissandra", "Sona", "Morgana", "Illaoi", "Blitzcrank", "Ivern Minion"],
        "level_plan": "Level to 8 and roll heavily for 5 Shepherd + a Vanguard frontline.",
        "double_up": "AP backline carry behind a Vanguard wall.",
        "counters": ["MR items", "Dive the backline"],
        "source": "tftacademy (17.6)"},
    "gnar_printer": {
        "name": "Gnar Printer (Meeple)", "carry": "Gnar", "playstyle": "reroll", "tier": "B",
        "traits": ["Meeple", "Timebreaker"],
        "carry_items": ["Guinsoo's Rageblade", "Deathblade", "Infinity Edge"],
        "early_units": ["Gnar", "Poppy"],
        "final_board": ["Gnar", "Poppy", "Ivern Minion", "Rammus", "Karma", "Galio", "Bard", "Jhin"],
        "level_plan": "Print Gnar 3-star with 7 Meeple at level 8, then drop to 5 Meeple and push 9 for 5-costs.",
        "double_up": "Meeple reroll — strong board quality, good anchor.",
        "counters": ["Out-scaled by 5-costs late"],
        "source": "tftacademy (17.6)"},
    "ap_shepherd_sona": {
        "name": "AP Shepherd (Sona 9-5)", "carry": "Sona", "playstyle": "fast9", "tier": "B",
        "traits": ["Shepherd", "Vanguard", "Psionic"],
        "carry_items": ["Blue Buff", "Morellonomicon", "Statikk Shiv"],
        "early_units": ["Sona", "Nunu", "Blitzcrank"],
        "final_board": ["Sona", "LeBlanc", "Mordekaiser", "Illaoi", "Rhaast", "Karma", "Nunu", "Blitzcrank", "Ivern Minion"],
        "level_plan": "Win-streak Vanguards, fast 9, itemize whichever upgraded unit you hit first.",
        "double_up": "AP fast-9 — frontline-heavy team anchor.",
        "counters": ["MR / dive backline"],
        "source": "tftacademy (17.6)"},
    "corki_riven": {
        "name": "Corki Riven (Meeple)", "carry": "Corki", "playstyle": "fast8", "tier": "B",
        "traits": ["Meeple", "Sniper", "Vanguard"],
        "carry_items": ["Last Whisper", "Deathblade", "Infinity Edge"],
        "early_units": ["Corki", "Rammus", "Riven"],
        "final_board": ["Corki", "Riven", "Rammus", "Galio", "Fizz", "Poppy", "Ivern Minion", "Milio"],
        "level_plan": "Win-streak Meeple/Snipers. Level 8, roll for Corki 2 + Rammus 2 + Riven, then push 9.",
        "double_up": "Backline Sniper carry; partner frontlines.",
        "counters": ["Gap-close to Corki", "Corner protects him"],
        "source": "tftacademy (17.6)"},
    "challenger_mf": {
        "name": "Challenger Miss Fortune", "carry": "Miss Fortune", "playstyle": "reroll", "tier": "B",
        "traits": ["Challenger", "Primordian"],
        "carry_items": ["Guinsoo's Rageblade", "Deathblade", "Giant Slayer"],
        "early_units": ["Miss Fortune", "Ornn"],
        "final_board": ["Miss Fortune", "Ornn", "Aatrox", "Maokai", "Rhaast", "Bel'Veth", "Jinx", "Kindred"],
        "level_plan": "Beginner reroll. Win-streak MF + Primordian, slow-roll stage 4 for 3-star MF.",
        "double_up": "Fast-attacking backline carry — pair with a tanky partner.",
        "counters": ["CC shuts her down", "Out-scaled late"],
        "source": "tftacademy (17.6)"},
    "nova_kindred": {
        "name": "N.O.V.A. Kindred", "carry": "Kindred", "playstyle": "fast8", "tier": "B",
        "traits": ["N.O.V.A.", "Brawler"],
        "carry_items": ["Guinsoo's Rageblade", "Runaan's Untamed Hurricane", "Giant Slayer"],
        "early_units": ["Kindred", "Caitlyn", "Aatrox"],
        "final_board": ["Aatrox", "Caitlyn", "Akali", "Bel'Veth", "Maokai", "Tahm Kench", "Kindred", "Morgana"],
        "level_plan": "Easy fast 8. Level 8, roll for Kindred 2 + Morgana 2; push 9 for 5-cost flex.",
        "double_up": "Backline carry with N.O.V.A. frontline — easy and stable.",
        "counters": ["Dive Kindred", "CC the carry"],
        "source": "tftacademy (17.6)"},
    "nova_reroll": {
        "name": "N.O.V.A. Reroll (Caitlyn)", "carry": "Caitlyn", "playstyle": "reroll", "tier": "C",
        "traits": ["N.O.V.A.", "Vanguard"],
        "carry_items": ["Guinsoo's Rageblade", "Runaan's Untamed Hurricane", "Giant Slayer"],
        "early_units": ["Caitlyn", "Aatrox"],
        "final_board": ["Aatrox", "Caitlyn", "Maokai", "Kindred", "Rammus", "Corki", "Shen", "Poppy"],
        "level_plan": "1-cost reroll. Slow-roll stage 3 for Caitlyn 3 + Aatrox 3, cap with Shen at 8-9.",
        "double_up": "Cheap backline carry — good early, cap with 4-costs.",
        "counters": ["Out-scaled late", "Dive the backline"],
        "source": "tftacademy (17.6)"},
    "karnami_flex": {
        "name": "KarNami Flex (Karma)", "carry": "Karma", "playstyle": "fast8", "tier": "B",
        "traits": ["Vanguard", "Voyager"],
        "carry_items": ["Statikk Shiv", "Spear of Shojin", "Morellonomicon"],
        "early_units": ["Karma", "Nami", "Nunu"],
        "final_board": ["Karma", "Nami", "Nunu", "Lissandra", "Illaoi", "Ivern Minion", "Bard", "Galio"],
        "level_plan": "AP opener behind 4 Vanguard. Fast 8 for Karma + Nami, push 9 for Bard/5-costs.",
        "double_up": "Vanguard frontline anchor with AP carry.",
        "counters": ["MR items", "Sustained DPS through frontline"],
        "source": "tftacademy (17.6)"},
    "fateweaver_tf": {
        "name": "Fateweaver Reroll (Twisted Fate)", "carry": "Twisted Fate", "playstyle": "reroll", "tier": "C",
        "traits": ["Fateweaver", "Rogue", "Vanguard"],
        "carry_items": ["Nashor's Tooth", "Rabadon's Deathcap", "Nashor's Tooth"],
        "early_units": ["Twisted Fate", "Jax", "Caitlyn"],
        "final_board": ["Aatrox", "Talon", "Caitlyn", "Twisted Fate", "Milio", "Jax", "Riven", "Corki"],
        "level_plan": "1-cost reroll. Slow-roll above 50g for 3-stars (TF > Jax > Cait/Talon > Aatrox).",
        "double_up": "AP backline carry — strong early reroll.",
        "counters": ["Out-scaled by legendaries", "MR"],
        "source": "tftacademy (17.6)"},
    "ez_cho": {
        "name": "Ez Cho (Brawler Sniper)", "carry": "Ezreal", "playstyle": "reroll", "tier": "C",
        "traits": ["Brawler", "Sniper", "Timebreaker"],
        "carry_items": ["Spear of Shojin", "Infinity Edge", "Deathblade"],
        "early_units": ["Cho'Gath", "Ezreal"],
        "final_board": ["Cho'Gath", "Ezreal", "Milio", "Pantheon", "Maokai", "Riven", "Tahm Kench", "Jhin"],
        "level_plan": "1-cost reroll. Don't level early; slow-roll above 50g for Ezreal + Cho, cap with Jhin.",
        "double_up": "Backline Sniper behind Brawlers; partner can frontline too.",
        "counters": ["Dive Ezreal", "Anti-heal vs Cho"],
        "source": "tftacademy (17.6)"},
    "anima_diana": {
        "name": "Anima Reroll (Diana)", "carry": "Diana", "playstyle": "reroll", "tier": "C",
        "traits": ["Anima", "Vanguard"],
        "carry_items": ["Guinsoo's Rageblade", "Titan's Resolve", "Sterak's Gage"],
        "early_units": ["Diana", "Illaoi", "Leona"],
        "final_board": ["Diana", "Illaoi", "Aurora", "Leblanc", "Jinx", "Leona", "Nunu", "Ivern Minion"],
        "level_plan": "3-cost reroll. HP-stack stage 2, slow-roll stage 4 for 3-star Diana, then level 8.",
        "double_up": "Bruiser frontline-carry — a sturdy anchor.",
        "counters": ["Anti-heal", "Out-scaled late"],
        "source": "tftacademy (17.6)"},
    "pyke_gwen": {
        "name": "Pyke Gwen (Psionic)", "carry": "Gwen", "playstyle": "reroll", "tier": "C",
        "traits": ["Psionic", "Vanguard", "Anima"],
        "carry_items": ["Rabadon's Deathcap", "Hextech Gunblade", "Jeweled Gauntlet"],
        "early_units": ["Gwen", "Pyke", "Pantheon"],
        "final_board": ["Gragas", "Ivern Minion", "Gwen", "Pantheon", "Pyke", "Rhaast", "Riven", "Nami"],
        "level_plan": "2-cost reroll. Level 6, roll for 2-cost upgrades; finish 3-stars then add Riven.",
        "double_up": "AP bruiser carry — easy reroll line.",
        "counters": ["Anti-heal vs Gwen", "Out-scaled late"],
        "source": "tftacademy (17.6)"},
    "viktor_nami": {
        "name": "Viktor B4L (Psionic)", "carry": "Viktor", "playstyle": "fast8", "tier": "C",
        "traits": ["Psionic", "Conduit", "Vanguard"],
        "carry_items": ["Jeweled Gauntlet", "Rabadon's Deathcap", "Statikk Shiv"],
        "early_units": ["Viktor", "Nami", "Lissandra"],
        "final_board": ["Lissandra", "Ivern Minion", "Mordekaiser", "Pyke", "Rhaast", "Illaoi", "Viktor", "Nami"],
        "level_plan": "Fast 8. Econ engine stage 2-3, level 8 for Viktor 2-star, push 9 for 5-costs.",
        "double_up": "AP frontline-carry anchor.",
        "counters": ["MR items", "Out-scaled late"],
        "source": "tftacademy (17.6)"},
    "lulu_reroll": {
        "name": "Fountain Lulu (Stargazer)", "carry": "Lulu", "playstyle": "reroll", "tier": "B",
        "traits": ["Stargazer", "Marauder"],
        "carry_items": ["Nashor's Tooth", "Nashor's Tooth", "Jeweled Gauntlet"],
        "early_units": ["Lulu", "Jax", "Milio"],
        "final_board": ["Aatrox", "Twisted Fate", "Jax", "Milio", "Pantheon", "Maokai", "Rhaast", "Lulu"],
        "level_plan": "3-cost reroll. Level 6 at 3-2, slow-roll stage 4 for 3-star Lulu, then level 8.",
        "double_up": "Support-carry hybrid — Stargazer gold fuels the team.",
        "counters": ["Burst Lulu down", "Out-scaled late"],
        "source": "tftacademy (17.6)"},
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


# ---- shop odds (public, deterministic) -> roll-timing math -------------------------
# Per-shop-slot % chance of each cost tier (1..5) at a given level. Standard TFT table;
# exact numbers drift slightly per set, but the SHAPE is stable — low levels favor cheap
# units, high levels favor expensive ones. Used to tell you the right level to roll for
# your carry, and when you're leveling PAST its odds.
SHOP_ODDS = {
    1:  (100, 0, 0, 0, 0),
    2:  (100, 0, 0, 0, 0),
    3:  (75, 25, 0, 0, 0),
    4:  (55, 30, 15, 0, 0),
    5:  (45, 33, 20, 2, 0),
    6:  (30, 40, 25, 5, 0),
    7:  (19, 30, 35, 15, 1),
    8:  (18, 25, 32, 22, 3),
    9:  (10, 20, 25, 35, 10),
    10: (5, 10, 20, 40, 25),
    11: (1, 2, 12, 50, 35),
}
_ROLL_LEVEL = {1: 6, 2: 7, 3: 7, 4: 8, 5: 9}   # the level you generally roll at, per carry cost

# Copies of EACH unit in the shared pool, by cost tier (standard TFT; varies a little per
# set). A 5-cost pool is tiny (9), so even a 2-star is a scramble once contested; a 1-cost
# pool (30) shrugs off light contest. Used to judge when a 3-star is realistically off.
POOL_SIZE = {1: 30, 2: 25, 3: 18, 4: 10, 5: 9}


def odds(level, cost):
    """% chance per shop slot of seeing a `cost`-cost unit at `level`."""
    if not level or not cost or not (1 <= cost <= 5):
        return 0
    row = SHOP_ODDS.get(max(1, min(int(level), 11)))
    return row[cost - 1] if row else 0


def roll_level_for(cost):
    """The level you generally roll at for a carry of this cost."""
    return _ROLL_LEVEL.get(cost, 8)


# Some hand-entered carry_items lists have copy-paste duplicates; a carry's build should
# show each item once. Dedupe in place (order-preserving) so every consumer gets clean data.
def _dedup_keep_order(seq):
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


for _c in COMPS.values():
    if _c.get("carry_items"):
        _c["carry_items"] = _dedup_keep_order(_c["carry_items"])


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


def comp_detail(key_or_carry):
    """Full 'what am I building' card for one comp: the board to collect, carry+items, plan.

    The board is the comp's curated final_board if present, else the early units plus the
    carry (the pieces you're collecting) — honest with the data we have.
    """
    c = find(key_or_carry)
    if not c:
        return None
    key = next((k for k, v in COMPS.items() if v is c), key_or_carry)
    carry = c.get("carry")
    board = list(c.get("final_board") or [])
    if not board:
        board = list(c.get("early_units") or [])
        if carry and carry.lower() != "flex" and carry not in board:
            board.append(carry)
    return {
        "key": key, "name": c.get("name"), "carry": carry,
        "playstyle": c.get("playstyle"),
        "traits": c.get("traits", []),
        "carry_items": c.get("carry_items", []),
        "early_units": c.get("early_units", []),
        "board": board,
        "level_plan": c.get("level_plan", ""),
        "double_up": c.get("double_up", ""),
        "source": c.get("source"),
    }


_TIER_RANK = {"S": 0, "A": 1, "A (Double Up)": 1, "B": 2, "C": 3}


def open_comps(contested_carries):
    """Comps whose carry is NOT being contested — the 'never assume, read the lobby' filter."""
    contested = {c.lower() for c in (contested_carries or [])}
    out = [c for c in COMPS.values() if c.get("carry", "").lower() not in contested]
    return sorted(out, key=lambda c: _TIER_RANK.get(c.get("tier"), 9))


def suggest_for_traits(active_traits, contested=None, current_key=None):
    """Build a comp FROM what the player is already fielding — no preset comp needed.

    active_traits = [{name, count}]. Picks the best meta comp whose DEFINING trait
    (traits[0]) matches the player's strongest active trait, uncontested, best tier;
    falls back to any comp that uses a strong active trait. Deterministic + free.

    current_key gives STICKINESS: if you've already committed to a comp and its defining
    trait is still within 1 of your strongest, keep it — don't flip the whole comp (and
    your item advice) on a single noisy read (e.g. traits misread on the item/God screen).
    """
    if not active_traits:
        return None
    contested = {c.lower() for c in (contested or [])}
    # Only traits at a real breakpoint (2+) drive the pick — a single stray unit of a trait
    # isn't a commitment and must not flip your comp (this caused spurious picks like Ez Cho
    # off a lone Brawler/Sniper on a noisy frame).
    strongest = sorted([t for t in active_traits if (t.get("count") or 0) >= 2],
                       key=lambda t: -(t.get("count") or 0))

    if current_key and current_key in COMPS:
        cur = COMPS[current_key]
        cur_def = next(iter([x.lower() for x in cur.get("traits", [])][:1]), None)
        top_count = strongest[0].get("count") if strongest else 0
        cur_count = next((t.get("count") or 0 for t in active_traits
                          if (t.get("name") or "").lower() == cur_def), 0)
        if (cur_def and cur.get("carry", "").lower() not in contested
                and cur_count + 1 >= top_count):     # still your line (within 1 of the top) -> stay
            return cur

    # NEW commitments need a CLEAR signal, not a lone breakpoint. The real bug was committing a
    # whole comp + item plan when four traits were tied at 2 (Space Groove/Bastion/Vanguard/Anima
    # = a flex board with no line) — it locked Nami off that. Commit only when there's a clear
    # strongest trait: 3+, OR a single UNAMBIGUOUS trait at 2 (a Primordian-heavy opener). Several
    # traits tied at 2 = flex, stay uncommitted. Stickiness above still holds an EXISTING line.
    top = strongest[0].get("count") or 0
    n_top = sum(1 for t in strongest if (t.get("count") or 0) == top)
    if top >= 3:
        commit = [t for t in strongest if (t.get("count") or 0) >= 3]
    elif top == 2 and n_top == 1:
        commit = [strongest[0]]          # one clear defining trait at 2 -> a real early line
    else:
        commit = []                      # tie at 2 (flex) -> don't lock a comp yet
    if not commit:                       # nothing clear enough to commit to -> stay flex
        return COMPS.get(current_key) if current_key in COMPS else None

    # 1. prefer a comp whose primary/defining trait IS your strongest clear trait
    for t in commit:
        tn = (t.get("name") or "").lower()
        if not tn:
            continue
        hits = [c for c in COMPS.values()
                if [x.lower() for x in c.get("traits", [])][:1] == [tn]
                and c.get("carry", "").lower() not in contested]
        if hits:
            return sorted(hits, key=lambda c: _TIER_RANK.get(c.get("tier"), 9))[0]

    # 2. fallback: any uncontested comp that uses one of your strong (3+) traits at all
    for t in commit:
        tn = (t.get("name") or "").lower()
        for c in sorted(COMPS.values(), key=lambda c: _TIER_RANK.get(c.get("tier"), 9)):
            if tn in [x.lower() for x in c.get("traits", [])] and c.get("carry", "").lower() not in contested:
                return c
    return None

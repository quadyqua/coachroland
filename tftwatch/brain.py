"""Coach Roland's reasoning brain — Phase 2.

Takes the full structured game state and asks an LLM to synthesize ONE coherent,
prioritized coaching plan instead of firing fixed template strings. It reasons over:

  - your comp + plan, and your Double Up partner's
  - the live lobby read (who's spiking on what, HP, your next opponent)
  - the contested lines
  - the game STAGE (early spikes are normal noise; late ones are commitment)
  - the AUGMENT LEDGER — augments chosen by YOU, your PARTNER, and each OPPONENT
    you've scouted. Augments are the strongest "are they actually committed?" and
    "what are they forcing?" signal in the game, so the brain leans on them for both
    contest permanence and predicting direction.

It outputs the same rec shape the dashboard already renders
({text, why, severity, priority, timer}), so timed choices still pin to the top with
a countdown. Grounded in compguide so it recommends real Set-17 comps, not invented
ones. It only ever SUGGESTS — every output is advice; you make the call.

    python -m tftwatch.brain --demo     # live call on your key, sample state -> printed coaching
"""
import os
import json

from openai import OpenAI

from . import compguide

DEFAULT_MODEL = os.getenv("OPENAI_COACH_MODEL", "gpt-4o")

_VALID_SEV = {"danger", "warn", "info", "buy"}


def _client(client=None) -> OpenAI:
    if client is not None:
        return client
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("No OPENAI_API_KEY found. Add it to .env.")
    return OpenAI(api_key=key)


def _meta_brief() -> str:
    """Compact, current grounding from compguide so the brain stays in sync with it."""
    def _line(k, c):
        s = (f"  - {c['name']} (key {k}): carry {c.get('carry')}, {c.get('playstyle')}, "
             f"tier {c.get('tier')}.")
        if c.get("traits"):
            s += f" TRAITS: {', '.join(c['traits'])}."
        if c.get("early_units"):
            s += f" EARLY BUYS: {', '.join(c['early_units'])}."
        if c.get("final_board"):
            s += f" FINAL BOARD (lvl 8-9): {', '.join(c['final_board'])}."
        if c.get("carry_items"):
            s += f" CARRY ITEMS: {', '.join(c['carry_items'])}."
        s += f" DoubleUp: {c.get('double_up', '')}"
        return s
    comps = "\n".join(_line(k, c) for k, c in compguide.COMPS.items())
    counters = "\n".join(f"  - vs {k}: {v}" for k, v in compguide.COUNTER_DYNAMICS.items())
    gods = "\n".join(f"  - {g}: {d.get('note', '')} ({d.get('variance')}-variance)"
                     for g, d in compguide.GODS.items())
    return (
        "PLAYSTYLE LEGEND: fast9 = weak early, scales to legendaries late; "
        "reroll = strong NOW, caps low; flex = adapts.\n"
        f"SET 17 COMPS (patch 17.6):\n{comps}\n\n"
        f"COUNTER DYNAMICS (positional/item/tempo — TFT has no comp-vs-comp matrix):\n{counters}\n\n"
        f"GODS (2 offered per game; pick offerings):\n{gods}\n\n"
        "AUGMENTS: no live augment win-rate data — judge each offered augment on comp fit "
        "(emblems that point your comp), stage (econ early, combat late), and whether it "
        "enables your carry. Do not assume a fixed top list.\n"
        "DOUBLE UP PRINCIPLES:\n  - " + "\n  - ".join(compguide.DOUBLE_UP_NOTES)
    )


_SYSTEM = """You are Coach Roland, coaching a COMPLETE BEGINNER at Teamfight Tactics Double Up
who does NOT know the jargon. Your job is to remove all guesswork: tell them exactly ONE
plan to commit to and exactly what to click, in plain English. You only ADVISE; they click.

HARD RULES:
0. GROUND THE COMP IN WHAT THEY'RE ALREADY BUILDING. If the state has me.active_traits, the
   comp you pick MUST match their strongest active trait(s) — e.g. "N.O.V.A. 5" -> a N.O.V.A.
   comp, not something unrelated. Do NOT pick a comp that ignores their board. Prefer the comp
   whose FIRST-listed trait (its defining trait) matches their strongest active trait — e.g.
   "Space Groove 6" -> the comp built primarily on Space Groove, not one that only uses it as a
   splash. And if committed_comp is set and their traits still support it, KEEP that comp — only
   switch if their traits clearly point elsewhere or it's badly contested. Never flip-flop.
1. COMMIT to a single comp from the provided meta and NAME it. Never say "consider X or Y",
   "play flex", or "go fast 9" with no explanation. A beginner needs a decision, not options.
2. Give a concrete SHOPPING LIST: name the specific units to buy (use the comp's EARLY BUYS),
   name the main carry, and name the items to put on the carry. "Buy any Caitlyn, Talon,
   Aatrox, or Jax you see in your shop."
3. NEVER use a term without defining it in the same breath. Examples:
   - "Fast 9 — save your gold, don't reroll, level up to 9, then buy strong units."
   - "Reroll — spend gold now to find 3-star (max-level) upgrades of cheap units."
   - "Econ — save up to 50 gold so you earn the most interest."
   - "Slam — combine item pieces right away instead of holding them."
   - "Contested — other players want the same units as you, so you'll struggle to find them."
4. LEAD with the single thing to do THIS moment (buy / level up / reroll / hold gold).
5. Each "why" is 1-2 short sentences a 10-year-old could follow.
6. If you don't know their gold/level/shop, still give the plan + a shopping list of what to
   watch for, and one simple default action (usually: "hold your gold, build your strongest
   board, slam item pieces").

DOUBLE UP + AUGMENTS (keep it simple for them):
   - Don't pick the same carry as your partner — you share units and starve each other.
   - If your partner is strong early, you pick a comp that's strong late, so you cover both.
   - If an opponent took an augment named after a unit/trait (an "emblem"), they're locked
     into that and it's a real fight — avoid copying them. Plain econ augments mean they
     might still change. Say when augments are UNKNOWN rather than guessing.

RIGHT-NOW SHOP & BENCH (when the state gives me.shop / me.gold / me.level):
   - Name the EXACT unit(s) in their shop to BUY now and why (it's a piece of your comp's
     board, or pairs with one you have). If nothing in shop fits, say "hold your gold —
     nothing to buy this shop." Make this a high-importance rec when something good is there.
   - Give a concrete econ call from gold + level: level up, reroll, or save — and define the
     term. e.g. "You're level 6 with 40+ gold — press Buy XP to reach level 7."
   - ALWAYS give a "what's next" step tied to me.level so they know the path AFTER early game:
     name the units to add as they level toward the FINAL BOARD, and when to roll. e.g.
     "Level 7 now: add [units]. At level 8, roll for [final-board pieces] and 2-star your carry."
   - If me.board_and_bench is given and the board looks full, name which unit to BENCH/REPLACE
     (pick one that is NOT in your comp's board). If you can't see their board, say "bench any
     unit that isn't in the list above."

LIVE PICK (state.offered): when state.offered is present (kind = god/augment; each option has a
name + effect), a time-boxed choice is on screen RIGHT NOW. This OVERRIDES the "first rec is the
comp" rule — your FIRST rec MUST be that pick, priority 100, timer ~30. Choose the option that
(a) best fits their strongest ACTIVE TRAITS and the board they're building (does its effect push
the comp they already have?), and (b) is NOT what the lobby is contesting. Name the exact option
and give a one-sentence why that references their trait. If state.offered is null, ignore this.

RIOT POLICY — keep it qualitative. Do NOT output augment win-rates, legend/God win-rates, or
augment average placements (numbers like "4.2 avg" or "18% top-4"). Riot's TFT third-party policy
prohibits showing these live. Say "strong pick this patch" / "best of the three", not a stat. Stat
review belongs post-game.

Return STRICT JSON only:
{"comp_key": "<EXACT compguide key IF a meta comp matches their strongest active trait, else null>",
 "comp_name": "<display name of the comp — name it after their strongest active trait if no meta comp fits, e.g. 'Space Groove'>",
 "comp_board": ["<~8 units to collect for this comp, grounded in their active traits + this set's roster>"],
 "recs": [
  {"text": "<short, concrete call a beginner can act on>",
   "why": "<1-2 plain sentences; define any term you use>",
   "severity": "danger|warn|info|buy",
   "priority": <0 normal, or 100 for a choice happening RIGHT NOW>,
   "timer": <seconds for a priority-100 choice, else null>}
]}
Pick comp_key from the meta ONLY if it matches their strongest active trait; otherwise set it
null and still fill comp_name + comp_board built around that trait. ALWAYS fill comp_name and
comp_board. Give 3-5 recs, most important first. The FIRST rec MUST be the comp + shopping list."""


def _state_brief(state: dict) -> str:
    return json.dumps(state, indent=2, ensure_ascii=False)


def advise(state: dict, model: str = None, client=None) -> dict:
    """state -> {comp_key, recs}: the committed comp + prioritized coaching recs."""
    model = model or DEFAULT_MODEL
    cli = _client(client)
    resp = cli.chat.completions.create(
        model=model,
        temperature=0.3,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": f"META (grounding):\n{_meta_brief()}\n\n"
                                        f"CURRENT GAME STATE:\n{_state_brief(state)}\n\n"
                                        f"Give me the plan."},
        ],
    )
    raw = json.loads(resp.choices[0].message.content)
    recs = [_coerce(r) for r in raw.get("recs", []) if isinstance(r, dict)]
    return {"comp_key": raw.get("comp_key"), "comp_name": raw.get("comp_name"),
            "comp_board": raw.get("comp_board"), "recs": recs}


def advise_text(situation: str, profile: str = "", model: str = None, client=None) -> list[dict]:
    """Free-text path: you describe the situation in plain English, get the same recs.

    Reliable on game one — no screen reading. `profile` is your standing setup (your
    comp + partner) prepended to every query so you don't retype it each round.
    """
    model = model or DEFAULT_MODEL
    cli = _client(client)
    intro = f"My standing setup: {profile}. " if profile else ""
    resp = cli.chat.completions.create(
        model=model,
        temperature=0.3,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": f"META (grounding):\n{_meta_brief()}\n\n"
                                        f"{intro}CURRENT SITUATION: {situation}\n\nGive me the plan."},
        ],
    )
    raw = json.loads(resp.choices[0].message.content)
    return [_coerce(r) for r in raw.get("recs", []) if isinstance(r, dict)]


def _coerce(r: dict) -> dict:
    sev = r.get("severity") if r.get("severity") in _VALID_SEV else "info"
    try:
        priority = int(r.get("priority") or 0)
    except (TypeError, ValueError):
        priority = 0
    timer = r.get("timer")
    try:
        timer = int(timer) if timer is not None else None
    except (TypeError, ValueError):
        timer = None
    return {"text": str(r.get("text", "")).strip(), "why": str(r.get("why", "")).strip(),
            "severity": sev, "priority": priority, "timer": timer, "stat": r.get("stat")}


# A realistic mid-game Double Up state, with augments known for all three parties.
_DEMO_STATE = {
    "stage": "4-2",
    "mode": "doubleup",
    "me": {"comp": "dark_star_jhin", "carry": "Jhin", "level": 8,
           "augments": ["Advanced Loan", "Stand United"]},
    "partner": {"name": "Wisp", "comp": "samira_reroll", "carry": "Samira", "level": 7,
                "augments": ["Cybernetic Implants", "Built Different"]},
    "opponents": [
        {"name": "AzAlways", "carry": "Vex",
         "augments": ["Vex (trait emblem)", "Final Ascension"]},   # locked -> real contest
        {"name": "KAORII", "carry": "Vex", "augments": ["Advanced Loan"]},  # only econ -> flexible
        {"name": "VowKeeper", "carry": "Master Yi", "augments": ["unknown (not scouted)"]},
        {"name": "Varianna", "carry": "Samira", "augments": ["unknown (not scouted)"]},
    ],
    "contested": ["Vex"],
    "next_opponent": "AzAlways (Vex)",
    "notes": "Steven mint (Team D) is on 8 HP holding 2 Jhin copies.",
}


def _demo() -> None:
    from dotenv import load_dotenv
    load_dotenv()
    out = advise(_DEMO_STATE)
    recs = out["recs"]
    print(f"\nCoach Roland (brain, {DEFAULT_MODEL}) — comp: {out.get('comp_key')} — "
          f"stage {_DEMO_STATE['stage']} Double Up\n" + "=" * 64)
    for r in sorted(recs, key=lambda r: -r.get("priority", 0)):
        head = ""
        if r.get("priority", 0) >= 100:
            head = "[DECIDE NOW" + (f" ~{r['timer']}s" if r.get("timer") else "") + "] "
        print(f"\n• {head}{r['text']}   ({r['severity']})")
        print(f"    why: {r['why']}")


if __name__ == "__main__":
    _demo()

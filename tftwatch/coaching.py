"""Pure coaching assembly — comp dicts + the deterministic rules-advice pipeline.

Lives apart from watcher.py on purpose: watcher pulls in mss/screen-capture, and the
simulator (and tests) must stay capture-free. These helpers only touch CoachRoland +
plain data, so both the live watcher and the offline simulator import them from here.
"""


def _comp_dicts(c):
    """Build the (my_comp, my_plan) dicts the coach wants from a comp-guide entry."""
    if not c:
        return None, None
    carry = c.get("carry")
    has_carry = bool(carry) and carry.lower() != "flex"
    my_comp = {
        "name": c.get("name"), "carry": carry,
        "carries": [carry] if has_carry else [],
        "carry_items": c.get("carry_items", []),
        "carry_components": c.get("carry_components", []),
        "flexible_components": c.get("flexible_components", []),
        "source": c.get("source"),
    }
    my_plan = {
        "name": c.get("name"), "carry": carry,
        "early_units": c.get("early_units"),
        "level_plan": c.get("level_plan"), "source": c.get("source"),
    }
    return my_comp, my_plan


def _rules_advice(coach, my_comp, my_plan, teammate_comp, data, contested, augs, alt_name,
                  stage=None, level=None, traits=None, rivals=None, scouted=None, stale=None,
                  hp=None, gold=None, ledger=None, last_scout=None):
    """Deterministic fallback advice (no LLM). Mirrors the brain's coverage cheaply."""
    out = []
    out += coach.level_pacing(stage, level, (my_comp or {}).get("playstyle"))
    out += coach.trait_advice(traits)
    out += coach.stabilize(hp, level, stage, gold, carry=(my_comp or {}).get("carry"),
                           early=(my_plan or {}).get("early_units"))
    # A scouted COMP counts as "known" too (not just a carry off the star-up feed), so we
    # don't nag you to scout someone you've already read.
    known = set(scouted or set()) | (set(ledger.comps) if ledger else set())
    out += coach.scout_prompt(data.get("players"), known, data.get("next_opponent"), stale=stale)
    # Counter the next opponent from a scouted read (their comp beats guessing). No-op until
    # a scout populates ledger.comp_for — the read/detection half is wired separately.
    nxt = data.get("next_opponent")
    if ledger and nxt and ledger.comp_for(nxt):
        out += coach.counter_comp(nxt, traits=ledger.comp_for(nxt),
                                  carry=ledger.carry_for(nxt), is_next=True)
    # Also surface the MOST RECENT scout even when we can't yet name whose board it was
    # (the "who" needs the scoreboard-highlight read, still to be calibrated). Skip if it's
    # already the named next-opponent counter above, so we don't double up.
    if last_scout and last_scout.get("traits"):
        owner = last_scout.get("owner")
        if not (owner and owner == nxt and ledger and ledger.comp_for(nxt)):
            out += coach.counter_comp(owner, traits=last_scout["traits"],
                                      carry=(ledger.carry_for(owner) if (ledger and owner) else None),
                                      is_next=bool(owner and owner == nxt))
    if my_comp:
        carry = my_comp.get("carry")
        has_carry = bool(my_comp.get("carries"))
        is_contested = has_carry and carry.lower() in {c.lower() for c in contested}
        if has_carry:
            out += coach.trouble(carry, rivals, alt=alt_name)   # "someone's on my carry" warn
            out += coach.pool_check(carry, len(rivals or []))   # pool-size-aware contest read
            out += coach.early_game(my_plan, stage=stage)
            out += coach.item_holder_advice(my_comp)
            out += coach.item_plan(my_comp, contested=is_contested, alt=alt_name)
        if teammate_comp:
            out += coach.doubleup(my_comp, teammate_comp, data, augments=augs, alt_comp=alt_name)
        else:
            out += coach.contested_pivot(my_comp, data, augments=augs, alt_comp=alt_name)
        out += coach.recommend(contested, my_intended=carry)
        out += coach.hard_switch(carry, contested, level,   # odds-aware pivot when contested
                                 avoid=(teammate_comp or {}).get("carries"))
    else:
        if teammate_comp:   # Double Up with no committed comp -> still coach the partnership
            out += coach.doubleup(my_comp or {}, teammate_comp, data, augments=augs, alt_comp=alt_name)
        out += coach.recommend(contested)
    return out

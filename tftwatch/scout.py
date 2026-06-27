"""Orchestration: take Riot IDs (or a live lobby) -> scouting reports."""
from dataclasses import dataclass, field

from .riot_client import RiotClient, RiotError
from .comps import extract_comp, aggregate, predict, tendencies, GameComp


@dataclass
class ScoutReport:
    riot_id: str
    rank: str
    games_analyzed: int
    set_number: int | None
    top_comps: list             # list[CompStat]
    prediction: dict
    error: str | None = None
    top_traits: list = field(default_factory=list)   # [{name, count, avg}]
    top_carries: list = field(default_factory=list)


def _rank_string(entries: list[dict]) -> str:
    for e in entries:
        if e.get("queueType") in (None, "RANKED_TFT"):
            tier = e.get("tier", "").title()
            div = e.get("rank", "")
            lp = e.get("leaguePoints", 0)
            if tier:
                return f"{tier} {div} ({lp} LP)"
    return "Unranked"


def scout_puuid(client: RiotClient, puuid: str, label: str, count: int) -> ScoutReport:
    try:
        match_ids = client.match_ids(puuid, count=count)
        if not match_ids:
            return ScoutReport(label, "?", 0, None, [], {}, error="no recent matches")

        comps: list[GameComp] = []
        current_set: int | None = None
        skipped_old_set = 0

        for mid in match_ids:
            m = client.match(mid)
            info = m.get("info", {})
            set_no = info.get("tft_set_number")
            if current_set is None:
                current_set = set_no
            if set_no != current_set:        # don't mix comps across sets
                skipped_old_set += 1
                continue
            me = next((p for p in info.get("participants", []) if p.get("puuid") == puuid), None)
            if me:
                comps.append(extract_comp(me))

        stats = aggregate(comps)
        pred = predict(stats, len(comps))
        traits_t, carries_t = tendencies(comps)
        rank = _rank_string(client.ranked(puuid))
        return ScoutReport(label, rank, len(comps), current_set, stats[:4], pred,
                           top_traits=traits_t[:5], top_carries=carries_t[:5])
    except RiotError as e:
        return ScoutReport(label, "?", 0, None, [], {}, error=str(e))


def scout_riot_id(client: RiotClient, riot_id: str, count: int) -> ScoutReport:
    if "#" not in riot_id:
        return ScoutReport(riot_id, "?", 0, None, [], {},
                           error="expected format Name#TAG")
    name, tag = riot_id.split("#", 1)
    try:
        acct = client.account_by_riot_id(name.strip(), tag.strip())
    except RiotError as e:
        return ScoutReport(riot_id, "?", 0, None, [], {}, error=str(e))
    return scout_puuid(client, acct["puuid"], riot_id, count)

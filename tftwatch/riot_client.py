"""Thin Riot TFT API client with disk caching and rate-limit handling.

Only read-only, official endpoints are used -> no Vanguard / ToS risk.
Match details are immutable, so we cache them to disk forever; this keeps
us comfortably under the dev-key limit (20 req/s, 100 req / 2 min).
"""
import json
import time
import pathlib
import urllib.parse

import requests

CACHE_DIR = pathlib.Path(__file__).resolve().parent.parent / ".cache" / "matches"


class RiotError(RuntimeError):
    pass


class RiotClient:
    def __init__(self, api_key: str, platform: str = "na1", region: str = "americas"):
        if not api_key:
            raise RiotError("No API key. Set RIOT_API_KEY in your .env file.")
        self.api_key = api_key
        self.platform = platform           # e.g. na1   (summoner / league / spectator)
        self.region = region               # e.g. americas (account / match)
        self.session = requests.Session()
        self.session.headers.update({"X-Riot-Token": api_key})
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # ---- low-level -------------------------------------------------------
    def _get(self, url: str, params: dict | None = None, _tries: int = 4) -> dict:
        for attempt in range(_tries):
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:  # rate limited - respect Retry-After
                wait = int(resp.headers.get("Retry-After", "5"))
                time.sleep(wait + 1)
                continue
            if resp.status_code == 404:
                raise RiotError(f"Not found (404): {url}")
            if resp.status_code in (401, 403):
                raise RiotError(
                    "Unauthorized (401/403). Your dev key likely expired -- "
                    "grab a fresh one at developer.riotgames.com."
                )
            if resp.status_code >= 500 and attempt < _tries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise RiotError(f"HTTP {resp.status_code} for {url}: {resp.text[:200]}")
        raise RiotError(f"Rate limited repeatedly on {url}")

    def _regional(self, path: str) -> str:
        return f"https://{self.region}.api.riotgames.com{path}"

    def _platform(self, path: str) -> str:
        return f"https://{self.platform}.api.riotgames.com{path}"

    # ---- public endpoints ------------------------------------------------
    def account_by_riot_id(self, game_name: str, tag_line: str) -> dict:
        name = urllib.parse.quote(game_name)
        tag = urllib.parse.quote(tag_line)
        return self._get(self._regional(f"/riot/account/v1/accounts/by-riot-id/{name}/{tag}"))

    def match_ids(self, puuid: str, count: int = 15) -> list[str]:
        return self._get(
            self._regional(f"/tft/match/v1/matches/by-puuid/{puuid}/ids"),
            params={"count": count},
        )

    def match(self, match_id: str) -> dict:
        cache_file = CACHE_DIR / f"{match_id}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8"))
        data = self._get(self._regional(f"/tft/match/v1/matches/{match_id}"))
        cache_file.write_text(json.dumps(data), encoding="utf-8")
        return data

    def ranked(self, puuid: str) -> list[dict]:
        try:
            return self._get(self._platform(f"/tft/league/v1/by-puuid/{puuid}"))
        except RiotError:
            return []

    # ---- experimental: auto-pull your current lobby ----------------------
    def active_lobby_puuids(self, puuid: str) -> list[str]:
        """Best-effort: read your active TFT game roster (the 'least manual' dream).

        The TFT Spectator endpoint path may need tweaking per Riot updates; it
        only returns data while you are actually in a game. Returns [] on failure
        so the CLI can fall back to manual Riot IDs.
        """
        try:
            data = self._get(
                self._platform(f"/lol/spectator/tft/v5/active-games/by-puuid/{puuid}")
            )
            return [p["puuid"] for p in data.get("participants", [])]
        except RiotError:
            return []

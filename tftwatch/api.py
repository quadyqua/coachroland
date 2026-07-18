"""HTTP API around the scout logic so it can run as a cloud service.

This is a thin web layer over scout_riot_id() — no scouting logic lives here.
The local watcher/vision/coach code is intentionally NOT imported; this service
is the cloud-able 'brain' half of TFTwatch (public Riot data only, no screen
reading), which keeps the image small and the deployment simple.
"""
import os
from dataclasses import asdict

from fastapi import FastAPI, HTTPException

from .riot_client import RiotClient, RiotError
from .scout import scout_riot_id

app = FastAPI(title="TFTwatch Scout API", version="0.1.0")

_match_cache = None


def _get_match_cache():
    """Build the Postgres cache once, if DB env vars are present.

    Returns None when PGHOST isn't set, so RiotClient falls back to its disk
    cache. Same image runs with or without a database attached.
    """
    global _match_cache
    if _match_cache is None and os.environ.get("PGHOST"):
        from .cache import PostgresMatchCache
        _match_cache = PostgresMatchCache()
    return _match_cache


def get_client() -> RiotClient:
    key = os.environ.get("RIOT_API_KEY")
    if not key:
        # 500: the operator misconfigured the deployment, not the caller's fault.
        raise HTTPException(status_code=500, detail="RIOT_API_KEY is not set")
    platform = os.environ.get("RIOT_PLATFORM", "na1")
    region = os.environ.get("RIOT_REGION", "americas")
    return RiotClient(key, platform=platform, region=region,
                      match_cache=_get_match_cache())


@app.get("/healthz")
def healthz():
    """Liveness/readiness probe target for Kubernetes. No external calls."""
    return {"status": "ok"}


@app.get("/scout")
def scout(riot_id: str, count: int = 15):
    """Scout one player: Name#TAG -> most-played comps + prediction."""
    client = get_client()
    report = scout_riot_id(client, riot_id, count)
    if report.error:
        # Upstream (Riot) or input problem -> 502 so callers can distinguish it.
        raise HTTPException(status_code=502, detail=report.error)
    return asdict(report)

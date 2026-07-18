"""Pluggable match-data caches.

TFT match data is immutable once a game ends, so caching it forever is safe --
and it's what keeps us comfortably under Riot's rate limit. The desktop client
caches to local disk; the cloud API service caches to Postgres so cached data
survives pod restarts. Both expose the same tiny get/set interface, so
RiotClient doesn't care which backend it's handed.
"""
import json
import pathlib


class DiskMatchCache:
    """Default cache: one JSON file per match under .cache/matches/."""

    def __init__(self, cache_dir: pathlib.Path | None = None):
        self.dir = cache_dir or (
            pathlib.Path(__file__).resolve().parent.parent / ".cache" / "matches"
        )
        self.dir.mkdir(parents=True, exist_ok=True)

    def get(self, match_id: str) -> dict | None:
        f = self.dir / f"{match_id}.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
        return None

    def set(self, match_id: str, data: dict) -> None:
        (self.dir / f"{match_id}.json").write_text(json.dumps(data), encoding="utf-8")


class PostgresMatchCache:
    """Cloud cache: one row per match in a Postgres table.

    With no explicit DSN, the connection uses standard libpq env vars
    (PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE) -- which is exactly how the
    Kubernetes deployment supplies them.
    """

    def __init__(self, dsn: str | None = None):
        import psycopg  # imported lazily so the desktop client never needs psycopg
        from psycopg.types.json import Jsonb

        self._psycopg = psycopg
        self._Jsonb = Jsonb
        self.dsn = dsn
        self._init_table()

    def _connect(self):
        return self._psycopg.connect(self.dsn) if self.dsn else self._psycopg.connect()

    def _init_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS match_cache ("
                "  match_id  text PRIMARY KEY,"
                "  data      jsonb NOT NULL,"
                "  cached_at timestamptz NOT NULL DEFAULT now()"
                ")"
            )

    def get(self, match_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM match_cache WHERE match_id = %s", (match_id,)
            ).fetchone()
            return row[0] if row else None

    def set(self, match_id: str, data: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO match_cache (match_id, data) VALUES (%s, %s) "
                "ON CONFLICT (match_id) DO NOTHING",
                (match_id, self._Jsonb(data)),
            )

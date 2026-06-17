"""
API-Football client with transparent SQLite caching.

Free tier is 100 requests/day, so caching is critical. Strategy:
- Finished fixtures cached forever (they don't change)
- Upcoming fixtures cached for 1 hour
- Live fixtures cached for 30 seconds
- Team/league metadata cached for 7 days
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_FOOTBALL_KEY", "")
API_HOST = os.getenv("API_FOOTBALL_HOST", "v3.football.api-sports.io")
DB_PATH = os.getenv("DB_PATH", "./copa.db")
WC_LEAGUE = int(os.getenv("WORLD_CUP_LEAGUE_ID", "1"))
WC_SEASON = int(os.getenv("WORLD_CUP_SEASON", "2026"))

BASE_URL = f"https://{API_HOST}"


class ApiFootballError(Exception):
    pass


class ApiFootballClient:
    """Thin wrapper around the API-Football REST API with cache."""

    def __init__(self, db_path: str = DB_PATH, api_key: str = API_KEY):
        if not api_key:
            raise ApiFootballError(
                "API_FOOTBALL_KEY missing. Sign up at dashboard.api-football.com"
            )
        self.api_key = api_key
        self.db_path = db_path
        self.session = requests.Session()
        self.session.headers.update(
            {"x-rapidapi-key": api_key, "x-rapidapi-host": API_HOST}
        )

    # ------------------------------------------------------------------
    # Cache layer
    # ------------------------------------------------------------------
    def _cache_key(self, path: str, params: dict[str, Any]) -> str:
        norm = path + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return sha256(norm.encode()).hexdigest()

    def _cache_get(self, key: str) -> dict | None:
        with sqlite3.connect(self.db_path) as con:
            row = con.execute(
                "SELECT response_json, expires_at FROM api_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
        if not row:
            return None
        expires = datetime.fromisoformat(row[1])
        if expires < datetime.now(timezone.utc):
            return None
        return json.loads(row[0])

    def _cache_set(self, key: str, payload: dict, ttl_seconds: int) -> None:
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=ttl_seconds)
        with sqlite3.connect(self.db_path) as con:
            con.execute(
                """INSERT OR REPLACE INTO api_cache
                   (cache_key, response_json, fetched_at, expires_at)
                   VALUES (?, ?, ?, ?)""",
                (key, json.dumps(payload), now.isoformat(), expires.isoformat()),
            )

    # ------------------------------------------------------------------
    # Core request
    # ------------------------------------------------------------------
    def _get(
        self, path: str, params: dict[str, Any] | None = None, ttl: int = 3600
    ) -> dict:
        params = params or {}
        key = self._cache_key(path, params)
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        resp = self.session.get(f"{BASE_URL}{path}", params=params, timeout=20)
        if resp.status_code != 200:
            raise ApiFootballError(f"{resp.status_code}: {resp.text[:200]}")
        payload = resp.json()
        if payload.get("errors"):
            raise ApiFootballError(str(payload["errors"]))
        self._cache_set(key, payload, ttl)
        return payload

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------
    def fixtures_world_cup(self) -> list[dict]:
        """All WC2026 fixtures. TTL 1h for upcoming, but finished are cached forever
        at the fixture level when we ingest them into the fixtures table."""
        payload = self._get(
            "/fixtures",
            params={"league": WC_LEAGUE, "season": WC_SEASON},
            ttl=3600,
        )
        return payload.get("response", [])

    def fixtures_by_team(
        self, team_id: int, season: int, last: int = 30
    ) -> list[dict]:
        """Historical fixtures for a team in a given season."""
        payload = self._get(
            "/fixtures",
            params={"team": team_id, "season": season, "last": last},
            ttl=86400,
        )
        return payload.get("response", [])

    def fixture_statistics(self, fixture_id: int) -> list[dict]:
        """Per-team statistics for a finished fixture."""
        payload = self._get(
            "/fixtures/statistics", params={"fixture": fixture_id}, ttl=86400 * 30
        )
        return payload.get("response", [])

    def head_to_head(self, home_id: int, away_id: int, last: int = 10) -> list[dict]:
        payload = self._get(
            "/fixtures/headtohead",
            params={"h2h": f"{home_id}-{away_id}", "last": last},
            ttl=86400,
        )
        return payload.get("response", [])

    def predictions(self, fixture_id: int) -> dict | None:
        """API-Football's built-in predictions (form, H2H, etc.)."""
        payload = self._get(
            "/predictions", params={"fixture": fixture_id}, ttl=3600
        )
        items = payload.get("response", [])
        return items[0] if items else None

    def teams_world_cup(self) -> list[dict]:
        payload = self._get(
            "/teams", params={"league": WC_LEAGUE, "season": WC_SEASON}, ttl=86400 * 7
        )
        return payload.get("response", [])


# Convenience singleton
_client: ApiFootballClient | None = None


def get_client() -> ApiFootballClient:
    global _client
    if _client is None:
        _client = ApiFootballClient()
    return _client

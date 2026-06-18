"""football-data.org client for World Cup fixtures and teams."""
from __future__ import annotations

import os
import json
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from typing import Any

from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("FOOTBALL_DATA_TOKEN", "")
BASE_URL = "https://api.football-data.org/v4"
WC_COMPETITION = "WC"
WC_SEASON = int(os.getenv("WORLD_CUP_SEASON", "2026"))


class FootballDataError(Exception):
    pass


class FootballDataClient:
    def __init__(self, api_token: str = API_TOKEN):
        if not api_token:
            raise FootballDataError("FOOTBALL_DATA_TOKEN missing.")
        self.api_token = api_token

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        query = urlencode(params or {})
        url = f"{BASE_URL}{path}" + (f"?{query}" if query else "")
        req = Request(url, headers={"X-Auth-Token": self.api_token})
        try:
            with urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise FootballDataError(f"{exc.code}: {body[:300]}") from exc

    def world_cup_matches(self, season: int = WC_SEASON) -> list[dict]:
        payload = self._get(
            f"/competitions/{WC_COMPETITION}/matches",
            params={"season": season},
        )
        return payload.get("matches", [])

    def world_cup_teams(self, season: int = WC_SEASON) -> list[dict]:
        payload = self._get(
            f"/competitions/{WC_COMPETITION}/teams",
            params={"season": season},
        )
        return payload.get("teams", [])


def get_client() -> FootballDataClient:
    return FootballDataClient()

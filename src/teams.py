"""Shared team-lookup helpers used by both the CLI and the API."""
from __future__ import annotations

import sqlite3


def resolve_team(con: sqlite3.Connection, name_or_code: str) -> tuple[int, str, str] | None:
    """Resolve a team by name, FIFA code, or country.

    Returns (id, name, code) or None. WC2026 teams win ties so that the
    predictor prefers a qualified squad when names collide.
    """
    row = con.execute(
        """SELECT id, name, COALESCE(code,'') FROM teams
           WHERE LOWER(name) = LOWER(?)
              OR LOWER(code) = LOWER(?)
              OR LOWER(country) = LOWER(?)
           ORDER BY is_wc2026 DESC
           LIMIT 1""",
        (name_or_code, name_or_code, name_or_code),
    ).fetchone()
    return row if row else None

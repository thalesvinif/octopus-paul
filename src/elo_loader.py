"""
Loads Elo ratings (from eloratings.net via Kaggle CSV) into SQLite.

Expected CSV columns (per the Kaggle dataset):
    team, code, year, end_of_year_elo, rank, ...

We store the most recent snapshot per team into the elo_ratings table.
For pre-Copa 2026 prior we use the snapshot closest to 2026-06-01.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = os.getenv("DB_PATH", "./copa.db")


def load_elo_csv(csv_path: str | Path, db_path: str = DB_PATH) -> int:
    """Load an Elo CSV into the elo_ratings table. Returns row count loaded."""
    df = pd.read_csv(csv_path)
    # Normalize column names
    df.columns = [c.lower() for c in df.columns]

    # Pick the canonical columns we care about; the Kaggle dataset uses
    # 'end_of_year_elo' as the rating field and 'code' for the 3-letter code.
    code_col = "code" if "code" in df.columns else "team_code"
    elo_col = next(
        (c for c in ("end_of_year_elo", "elo", "rating") if c in df.columns), None
    )
    if elo_col is None:
        raise ValueError(f"No Elo column found. Available: {list(df.columns)}")

    # Build snapshot_date from year (use Dec 31 of that year)
    if "snapshot_date" not in df.columns and "year" in df.columns:
        df["snapshot_date"] = df["year"].astype(int).astype(str) + "-12-31"

    rank_col = "rank" if "rank" in df.columns else None

    out = df[[code_col, "snapshot_date", elo_col] + ([rank_col] if rank_col else [])].copy()
    out.columns = ["team_code", "snapshot_date", "elo"] + (["rank"] if rank_col else [])
    out = out.dropna(subset=["team_code", "elo"])

    with sqlite3.connect(db_path) as con:
        if "rank" in out.columns:
            con.executemany(
                """INSERT OR REPLACE INTO elo_ratings
                   (team_code, snapshot_date, elo, rank)
                   VALUES (?, ?, ?, ?)""",
                out.itertuples(index=False, name=None),
            )
        else:
            con.executemany(
                """INSERT OR REPLACE INTO elo_ratings
                   (team_code, snapshot_date, elo)
                   VALUES (?, ?, ?)""",
                out.itertuples(index=False, name=None),
            )
    return len(out)


def latest_elo(team_code: str, on_or_before: str | None = None, db_path: str = DB_PATH) -> float | None:
    """Return the most recent Elo rating for a team up to a given date (inclusive)."""
    with sqlite3.connect(db_path) as con:
        if on_or_before:
            row = con.execute(
                """SELECT elo FROM elo_ratings
                   WHERE team_code = ? AND snapshot_date <= ?
                   ORDER BY snapshot_date DESC LIMIT 1""",
                (team_code, on_or_before),
            ).fetchone()
        else:
            row = con.execute(
                """SELECT elo FROM elo_ratings
                   WHERE team_code = ?
                   ORDER BY snapshot_date DESC LIMIT 1""",
                (team_code,),
            ).fetchone()
    return float(row[0]) if row else None


def all_latest_elo(on_or_before: str | None = None, db_path: str = DB_PATH) -> dict[str, float]:
    """Latest Elo for every team in the table."""
    with sqlite3.connect(db_path) as con:
        if on_or_before:
            rows = con.execute(
                """SELECT team_code, elo FROM elo_ratings e1
                   WHERE snapshot_date = (
                       SELECT MAX(snapshot_date) FROM elo_ratings e2
                       WHERE e2.team_code = e1.team_code
                         AND e2.snapshot_date <= ?
                   )""",
                (on_or_before,),
            ).fetchall()
        else:
            rows = con.execute(
                """SELECT team_code, elo FROM elo_ratings e1
                   WHERE snapshot_date = (
                       SELECT MAX(snapshot_date) FROM elo_ratings e2
                       WHERE e2.team_code = e1.team_code
                   )"""
            ).fetchall()
    return {code: float(elo) for code, elo in rows}

"""
Feature engineering for both prediction models.

Modelo A (Histórico)  uses build_historical_features → DataFrame for training.
Modelo B (Tournament-only) uses build_tournament_state → per-team running stats.
"""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from .elo_loader import all_latest_elo, latest_elo

DB_PATH = os.getenv("DB_PATH", "./copa.db")


# ======================================================================
# Modelo A — Historical features
# ======================================================================
@dataclass
class MatchFeatures:
    """Feature row for a single fixture, either for training or inference."""

    fixture_id: int | None
    home_team_id: int
    away_team_id: int
    date_utc: str
    home_elo: float
    away_elo: float
    elo_diff: float
    home_form_gf: float          # goals scored per game, last 10
    home_form_ga: float          # goals conceded per game, last 10
    away_form_gf: float
    away_form_ga: float
    h2h_home_winrate: float      # last 10 H2H meetings
    h2h_avg_goals: float
    home_rest_days: float
    away_rest_days: float
    is_neutral: int
    home_goals: int | None = None    # set only for training rows
    away_goals: int | None = None


def _team_form(con: sqlite3.Connection, team_id: int, before_date: str, n: int = 10) -> tuple[float, float]:
    """Return (avg goals scored, avg goals conceded) over the last `n` matches."""
    rows = con.execute(
        """SELECT home_team_id, away_team_id, home_goals, away_goals
           FROM fixtures
           WHERE (home_team_id = ? OR away_team_id = ?)
             AND date_utc < ?
             AND status = 'FT'
             AND home_goals IS NOT NULL
           ORDER BY date_utc DESC LIMIT ?""",
        (team_id, team_id, before_date, n),
    ).fetchall()
    if not rows:
        return 1.2, 1.2  # neutral prior
    gf, ga = 0, 0
    for h, a, hg, ag in rows:
        if h == team_id:
            gf += hg; ga += ag
        else:
            gf += ag; ga += hg
    return gf / len(rows), ga / len(rows)


def _h2h(con: sqlite3.Connection, home_id: int, away_id: int, before_date: str, n: int = 10) -> tuple[float, float]:
    """Return (home_winrate_in_h2h, avg_goals_per_h2h)."""
    rows = con.execute(
        """SELECT home_team_id, home_goals, away_goals
           FROM fixtures
           WHERE ((home_team_id = ? AND away_team_id = ?)
                  OR (home_team_id = ? AND away_team_id = ?))
             AND date_utc < ?
             AND status = 'FT'
             AND home_goals IS NOT NULL
           ORDER BY date_utc DESC LIMIT ?""",
        (home_id, away_id, away_id, home_id, before_date, n),
    ).fetchall()
    if not rows:
        return 0.5, 2.5
    home_wins = 0
    total_goals = 0
    for h, hg, ag in rows:
        total_goals += hg + ag
        is_home_pov = h == home_id
        if (is_home_pov and hg > ag) or (not is_home_pov and ag > hg):
            home_wins += 1
    return home_wins / len(rows), total_goals / len(rows)


def _rest_days(con: sqlite3.Connection, team_id: int, before_date: str) -> float:
    row = con.execute(
        """SELECT date_utc FROM fixtures
           WHERE (home_team_id = ? OR away_team_id = ?)
             AND date_utc < ?
             AND status = 'FT'
           ORDER BY date_utc DESC LIMIT 1""",
        (team_id, team_id, before_date),
    ).fetchone()
    if not row:
        return 14.0
    last = datetime.fromisoformat(row[0].replace("Z", "")).replace(tzinfo=None)
    cur = datetime.fromisoformat(before_date.replace("Z", "").split("+")[0]).replace(tzinfo=None)
    return max(0.0, (cur - last).total_seconds() / 86400)


def _team_code(con: sqlite3.Connection, team_id: int) -> str | None:
    row = con.execute("SELECT code FROM teams WHERE id = ?", (team_id,)).fetchone()
    return row[0] if row else None


def build_features_for_match(
    home_team_id: int,
    away_team_id: int,
    date_utc: str,
    is_neutral: int = 1,
    db_path: str = DB_PATH,
) -> MatchFeatures:
    """Compute Modelo A features for one fixture at a given date."""
    with sqlite3.connect(db_path) as con:
        home_code = _team_code(con, home_team_id)
        away_code = _team_code(con, away_team_id)
        date_only = date_utc[:10]
        home_elo = latest_elo(home_code or "", on_or_before=date_only) or 1500
        away_elo = latest_elo(away_code or "", on_or_before=date_only) or 1500
        h_gf, h_ga = _team_form(con, home_team_id, date_utc)
        a_gf, a_ga = _team_form(con, away_team_id, date_utc)
        h2h_wr, h2h_avg = _h2h(con, home_team_id, away_team_id, date_utc)
        h_rest = _rest_days(con, home_team_id, date_utc)
        a_rest = _rest_days(con, away_team_id, date_utc)

    return MatchFeatures(
        fixture_id=None,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        date_utc=date_utc,
        home_elo=home_elo,
        away_elo=away_elo,
        elo_diff=home_elo - away_elo,
        home_form_gf=h_gf,
        home_form_ga=h_ga,
        away_form_gf=a_gf,
        away_form_ga=a_ga,
        h2h_home_winrate=h2h_wr,
        h2h_avg_goals=h2h_avg,
        home_rest_days=h_rest,
        away_rest_days=a_rest,
        is_neutral=is_neutral,
    )


def build_training_set(
    db_path: str = DB_PATH, since: str = "2020-01-01", exclude_wc2026: bool = False
):
    """Build a training DataFrame from finished historical fixtures.

    Set exclude_wc2026=True for a leak-free backtest of the WC2026 matches
    (otherwise those games are both trained on and tested).
    """
    import pandas as pd

    with sqlite3.connect(db_path) as con:
        fxs = con.execute(
            f"""SELECT id, home_team_id, away_team_id, date_utc, home_goals, away_goals
               FROM fixtures
               WHERE status = 'FT'
                 AND home_goals IS NOT NULL
                 AND date_utc >= ?
                 {"AND is_wc2026 = 0" if exclude_wc2026 else ""}
               ORDER BY date_utc""",
            (since,),
        ).fetchall()

    records = []
    for fid, h_id, a_id, date, hg, ag in fxs:
        f = build_features_for_match(h_id, a_id, date, is_neutral=1, db_path=db_path)
        records.append(
            {
                "fixture_id": fid,
                "elo_diff": f.elo_diff,
                "home_form_gf": f.home_form_gf,
                "home_form_ga": f.home_form_ga,
                "away_form_gf": f.away_form_gf,
                "away_form_ga": f.away_form_ga,
                "h2h_home_winrate": f.h2h_home_winrate,
                "h2h_avg_goals": f.h2h_avg_goals,
                "home_rest": f.home_rest_days,
                "away_rest": f.away_rest_days,
                "is_neutral": f.is_neutral,
                "home_goals": hg,
                "away_goals": ag,
            }
        )
    return pd.DataFrame(records)


# ======================================================================
# Modelo B — Tournament-only state
# ======================================================================
@dataclass
class TournamentTeamState:
    """Per-team running state from WC2026 matches only."""

    team_id: int
    team_code: str
    matches_played: int
    goals_scored_total: int
    goals_conceded_total: int
    prior_elo: float                 # pre-tournament Elo (used as Bayesian prior)


def build_tournament_state(db_path: str = DB_PATH) -> dict[int, TournamentTeamState]:
    """Aggregate each team's performance using only WC2026 finished matches."""
    pre_tournament_elo = all_latest_elo(on_or_before="2026-06-10")  # day before kickoff
    with sqlite3.connect(db_path) as con:
        teams = con.execute(
            "SELECT id, code FROM teams WHERE is_wc2026 = 1"
        ).fetchall()
        state: dict[int, TournamentTeamState] = {}
        for tid, code in teams:
            rows = con.execute(
                """SELECT home_team_id, home_goals, away_goals
                   FROM fixtures
                   WHERE is_wc2026 = 1
                     AND status = 'FT'
                     AND home_goals IS NOT NULL
                     AND (home_team_id = ? OR away_team_id = ?)""",
                (tid, tid),
            ).fetchall()
            gs = gc = 0
            for h, hg, ag in rows:
                if h == tid:
                    gs += hg; gc += ag
                else:
                    gs += ag; gc += hg
            state[tid] = TournamentTeamState(
                team_id=tid,
                team_code=code or "",
                matches_played=len(rows),
                goals_scored_total=gs,
                goals_conceded_total=gc,
                prior_elo=pre_tournament_elo.get(code or "", 1500),
            )
    return state

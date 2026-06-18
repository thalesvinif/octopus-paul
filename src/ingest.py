"""
Ingest pipeline. Pulls from API-Football into the SQLite database.

Usage:
    python -m src.ingest world-cup           # WC2026 fixtures + stats
    python -m src.ingest history --years 5   # historical matches per WC2026 team
    python -m src.ingest elo --csv path.csv  # Elo ratings CSV
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime

import click

from .football_data import get_client as get_football_data_client

DB_PATH = os.getenv("DB_PATH", "./copa.db")


def _upsert_team(con: sqlite3.Connection, team: dict, is_wc2026: int = 0) -> None:
    con.execute(
        """INSERT INTO teams (id, name, code, country, flag_url, is_wc2026)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             name = excluded.name,
             code = COALESCE(excluded.code, teams.code),
             flag_url = excluded.flag_url,
             is_wc2026 = MAX(teams.is_wc2026, excluded.is_wc2026)""",
        (
            team["id"],
            team.get("name"),
            team.get("code"),
            team.get("country"),
            team.get("logo") or team.get("flag"),
            is_wc2026,
        ),
    )


def _upsert_fixture(con: sqlite3.Connection, fx: dict, is_wc2026: int) -> None:
    fixture = fx["fixture"]
    league = fx["league"]
    teams = fx["teams"]
    goals = fx.get("goals", {})
    score = fx.get("score", {}).get("halftime", {})
    venue = fixture.get("venue") or {}

    _upsert_team(con, teams["home"], is_wc2026)
    _upsert_team(con, teams["away"], is_wc2026)

    con.execute(
        """INSERT INTO fixtures (
              id, league_id, season, round, date_utc, venue_city, venue_country,
              is_neutral, status, home_team_id, away_team_id,
              home_goals, away_goals, home_goals_ht, away_goals_ht, is_wc2026
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             status = excluded.status,
             home_goals = excluded.home_goals,
             away_goals = excluded.away_goals,
             home_goals_ht = excluded.home_goals_ht,
             away_goals_ht = excluded.away_goals_ht""",
        (
            fixture["id"],
            league["id"],
            league["season"],
            league.get("round"),
            fixture["date"],
            venue.get("city"),
            venue.get("name"),
            1,  # WC2026 mostly neutral; refine per host country if needed
            fixture["status"]["short"],
            teams["home"]["id"],
            teams["away"]["id"],
            goals.get("home"),
            goals.get("away"),
            score.get("home"),
            score.get("away"),
            is_wc2026,
        ),
    )


def _upsert_stats(con: sqlite3.Connection, fixture_id: int, stats_response: list[dict]) -> None:
    """API-Football statistics format: response[team]['statistics'][i] = {type, value}."""
    KEYS = {
        "Total Shots": "shots_total",
        "Shots on Goal": "shots_on_target",
        "Shots insidebox": "shots_inside_box",
        "Ball Possession": "possession_pct",
        "Total passes": "passes_total",
        "Passes %": "passes_accuracy_pct",
        "Fouls": "fouls",
        "Corner Kicks": "corners",
        "Offsides": "offsides",
        "Yellow Cards": "yellow_cards",
        "Red Cards": "red_cards",
        "expected_goals": "xg",
    }
    for team_stats in stats_response:
        team_id = team_stats["team"]["id"]
        cols: dict[str, float | int | None] = {v: None for v in KEYS.values()}
        for stat in team_stats.get("statistics", []):
            col = KEYS.get(stat["type"])
            if not col:
                continue
            val = stat.get("value")
            if isinstance(val, str) and val.endswith("%"):
                val = float(val.rstrip("%"))
            cols[col] = val
        con.execute(
            f"""INSERT OR REPLACE INTO match_stats (
                   fixture_id, team_id, {", ".join(cols.keys())}
                ) VALUES (?, ?, {", ".join("?" * len(cols))})""",
            (fixture_id, team_id, *cols.values()),
        )


def _football_data_status(status: str) -> str:
    return {
        "FINISHED": "FT",
        "IN_PLAY": "1H",
        "PAUSED": "HT",
        "TIMED": "NS",
        "SCHEDULED": "NS",
        "POSTPONED": "PST",
        "SUSPENDED": "SUSP",
        "CANCELLED": "CANC",
    }.get(status, status)


def _upsert_football_data_team(
    con: sqlite3.Connection, team: dict, is_wc2026: int = 1
) -> None:
    if not team.get("id"):
        return
    con.execute(
        """INSERT INTO teams (id, name, code, country, flag_url, is_wc2026)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             name = excluded.name,
             code = COALESCE(excluded.code, teams.code),
             country = COALESCE(excluded.country, teams.country),
             flag_url = COALESCE(excluded.flag_url, teams.flag_url),
             is_wc2026 = MAX(teams.is_wc2026, excluded.is_wc2026)""",
        (
            team["id"],
            team.get("name") or team.get("shortName") or team.get("tla"),
            team.get("tla"),
            team.get("area", {}).get("name") or team.get("name"),
            team.get("crest"),
            is_wc2026,
        ),
    )


def _upsert_football_data_fixture(con: sqlite3.Connection, match: dict) -> bool:
    home = match.get("homeTeam") or {}
    away = match.get("awayTeam") or {}
    if not home.get("id") or not away.get("id"):
        return False

    _upsert_football_data_team(con, home, is_wc2026=1)
    _upsert_football_data_team(con, away, is_wc2026=1)

    score = match.get("score") or {}
    full_time = score.get("fullTime") or {}
    half_time = score.get("halfTime") or {}
    season = match.get("season") or {}
    competition = match.get("competition") or {}
    group = match.get("group")
    stage = match.get("stage")
    matchday = match.get("matchday")
    round_name = group or stage
    if matchday and round_name:
        round_name = f"{round_name} - Matchday {matchday}"

    con.execute(
        """INSERT INTO fixtures (
              id, league_id, season, round, date_utc, venue_city, venue_country,
              is_neutral, status, home_team_id, away_team_id,
              home_goals, away_goals, home_goals_ht, away_goals_ht, is_wc2026
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             round = excluded.round,
             date_utc = excluded.date_utc,
             status = excluded.status,
             home_team_id = excluded.home_team_id,
             away_team_id = excluded.away_team_id,
             home_goals = excluded.home_goals,
             away_goals = excluded.away_goals,
             home_goals_ht = excluded.home_goals_ht,
             away_goals_ht = excluded.away_goals_ht,
             is_wc2026 = excluded.is_wc2026""",
        (
            match["id"],
            competition.get("id", 2000),
            int(season.get("startDate", "2026")[:4]),
            round_name,
            match["utcDate"],
            None,
            None,
            1,
            _football_data_status(match.get("status", "")),
            home["id"],
            away["id"],
            full_time.get("home"),
            full_time.get("away"),
            half_time.get("home"),
            half_time.get("away"),
            1,
        ),
    )
    return True


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
@click.group()
def cli():
    """Copa Predictor ingest pipeline."""


@cli.command("world-cup")
def ingest_wc():
    """Ingest WC2026 fixtures and stats from finished matches."""
    from .api_football import get_client

    client = get_client()
    fixtures = client.fixtures_world_cup()
    click.echo(f"Found {len(fixtures)} WC2026 fixtures")

    finished = 0
    with sqlite3.connect(DB_PATH) as con:
        for fx in fixtures:
            _upsert_fixture(con, fx, is_wc2026=1)
            if fx["fixture"]["status"]["short"] == "FT":
                finished += 1

    # Pull stats for finished matches only (saves quota)
    click.echo(f"Pulling stats for {finished} finished matches...")
    with sqlite3.connect(DB_PATH) as con:
        for fx in fixtures:
            if fx["fixture"]["status"]["short"] != "FT":
                continue
            fid = fx["fixture"]["id"]
            stats = client.fixture_statistics(fid)
            if stats:
                _upsert_stats(con, fid, stats)

    click.echo("✓ World Cup ingest complete")


def refresh_world_cup_results(replace: bool = False) -> dict:
    """Pull WC2026 fixtures/scores from football-data.org into SQLite.

    Reusable by both the CLI and the API. Returns a summary dict.
    """
    client = get_football_data_client()
    teams = client.world_cup_teams()
    matches = client.world_cup_matches()

    with sqlite3.connect(DB_PATH) as con:
        if replace:
            con.execute(
                """DELETE FROM match_stats
                   WHERE fixture_id IN (SELECT id FROM fixtures WHERE is_wc2026 = 1)"""
            )
            con.execute("DELETE FROM fixtures WHERE is_wc2026 = 1")
            con.execute("UPDATE teams SET is_wc2026 = 0 WHERE is_wc2026 = 1")

        for team in teams:
            _upsert_football_data_team(con, team, is_wc2026=1)

        inserted = 0
        skipped = 0
        finished = 0
        for match in matches:
            if _upsert_football_data_fixture(con, match):
                inserted += 1
                if match.get("status") == "FINISHED":
                    finished += 1
            else:
                skipped += 1

    return {
        "teams": len(teams),
        "fixtures": inserted,
        "finished": finished,
        "skipped": skipped,
    }


@cli.command("world-cup-football-data")
@click.option("--replace", is_flag=True, help="Delete existing WC2026 fixtures first")
def ingest_wc_football_data(replace: bool):
    """Ingest WC2026 fixtures and scores from football-data.org."""
    r = refresh_world_cup_results(replace=replace)
    click.echo(f"Found {r['teams']} WC2026 teams")
    click.echo(
        f"✓ football-data.org ingest complete: {r['fixtures']} fixtures, "
        f"{r['finished']} finished, {r['skipped']} unresolved knockout placeholders skipped"
    )


@cli.command("history")
@click.option("--years", default=5, help="Number of past years to pull per team")
def ingest_history(years: int):
    """Ingest historical fixtures for every WC2026 team."""
    from .api_football import get_client

    client = get_client()
    with sqlite3.connect(DB_PATH) as con:
        teams = con.execute(
            "SELECT id, name FROM teams WHERE is_wc2026 = 1"
        ).fetchall()

    current_year = datetime.utcnow().year
    seasons = list(range(current_year - years, current_year + 1))

    for team_id, name in teams:
        click.echo(f"Pulling {name} history...")
        for season in seasons:
            try:
                fixtures = client.fixtures_by_team(team_id, season, last=50)
            except Exception as e:  # noqa: BLE001
                click.echo(f"  skip {season}: {e}", err=True)
                continue
            with sqlite3.connect(DB_PATH) as con:
                for fx in fixtures:
                    _upsert_fixture(con, fx, is_wc2026=0)
    click.echo("✓ History ingest complete")


@cli.command("elo")
@click.option("--csv", "csv_path", required=True, help="Path to Elo CSV file")
def ingest_elo(csv_path: str):
    """Load Elo ratings CSV into the database."""
    from .elo_loader import load_elo_csv

    n = load_elo_csv(csv_path)
    click.echo(f"✓ Loaded {n} Elo rows")


if __name__ == "__main__":
    cli()

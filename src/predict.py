"""
Predict a single fixture using both models, side by side.

Usage:
    python -m src.predict --home Brasil --away Argentina
    python -m src.predict --fixture-id 1234567
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

import click
from rich.console import Console
from rich.table import Table

from .features import build_features_for_match, build_tournament_state
from .models import HistoricalModel, TournamentModel, Prediction

DB_PATH = os.getenv("DB_PATH", "./copa.db")
console = Console()


def _resolve_team(con: sqlite3.Connection, name_or_code: str) -> tuple[int, str, str] | None:
    row = con.execute(
        """SELECT id, name, COALESCE(code,'') FROM teams
           WHERE LOWER(name) = LOWER(?)
              OR LOWER(code) = LOWER(?)
              OR LOWER(country) = LOWER(?)
           LIMIT 1""",
        (name_or_code, name_or_code, name_or_code),
    ).fetchone()
    return row if row else None


def _render_prediction(p: Prediction) -> None:
    title = {
        "historical": "Modelo A — Histórico",
        "tournament": "Modelo B — Apenas Copa 2026",
    }[p.model]
    t = Table(title=title, show_header=False, expand=False)
    t.add_column(style="bold cyan")
    t.add_column()
    t.add_row("Gols esperados (casa)", f"{p.expected_home:.2f}")
    t.add_row("Gols esperados (visit.)", f"{p.expected_away:.2f}")
    t.add_row(
        "Placar mais provável",
        f"{p.most_likely[0]} × {p.most_likely[1]}  ({p.most_likely[2] * 100:.1f}%)",
    )
    t.add_row("P(vitória casa)", f"{p.p_home_win * 100:.1f}%")
    t.add_row("P(empate)", f"{p.p_draw * 100:.1f}%")
    t.add_row("P(vitória visit.)", f"{p.p_away_win * 100:.1f}%")
    if p.notes:
        t.add_row("Notas", p.notes)
    console.print(t)


@click.command()
@click.option("--home", help="Home team name, code, or country")
@click.option("--away", help="Away team name, code, or country")
@click.option("--fixture-id", type=int, help="Predict a specific WC2026 fixture")
@click.option(
    "--date", default=None, help="Match date (ISO). Defaults to now or fixture date"
)
def predict(home: str | None, away: str | None, fixture_id: int | None, date: str | None):
    """Predict a fixture with both Modelo A and Modelo B."""
    with sqlite3.connect(DB_PATH) as con:
        if fixture_id:
            row = con.execute(
                """SELECT home_team_id, away_team_id, date_utc
                   FROM fixtures WHERE id = ?""",
                (fixture_id,),
            ).fetchone()
            if not row:
                raise click.ClickException(f"Fixture {fixture_id} not found")
            home_id, away_id, fixture_date = row
            date = date or fixture_date
        else:
            if not home or not away:
                raise click.ClickException("Provide --home and --away, or --fixture-id")
            h = _resolve_team(con, home)
            a = _resolve_team(con, away)
            if not h:
                raise click.ClickException(f"Home team '{home}' not found")
            if not a:
                raise click.ClickException(f"Away team '{away}' not found")
            home_id, _, _ = h
            away_id, _, _ = a
            date = date or datetime.now(timezone.utc).isoformat()

        home_name = con.execute("SELECT name FROM teams WHERE id = ?", (home_id,)).fetchone()[0]
        away_name = con.execute("SELECT name FROM teams WHERE id = ?", (away_id,)).fetchone()[0]

    console.rule(f"[bold]{home_name} × {away_name}[/bold]   ({date[:10]})")

    # --- Modelo A ---
    try:
        model_a = HistoricalModel.load()
        feats = build_features_for_match(home_id, away_id, date)
        pred_a = model_a.predict(feats)
        _render_prediction(pred_a)
    except FileNotFoundError:
        console.print(
            "[yellow]Modelo A não treinado. Rode `python -m src.models train-historical` primeiro.[/yellow]"
        )

    # --- Modelo B ---
    state = build_tournament_state()
    if home_id not in state or away_id not in state:
        console.print(
            "[yellow]Modelo B exige times qualificados para a Copa 2026.[/yellow]"
        )
        return
    model_b = TournamentModel()
    pred_b = model_b.predict(state[home_id], state[away_id])
    _render_prediction(pred_b)


if __name__ == "__main__":
    predict()

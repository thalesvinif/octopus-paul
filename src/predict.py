"""
Predict a single fixture.

Usage:
    python -m src.predict --home Brazil --away Argentina
    python -m src.predict --fixture-id 537339
    python -m src.predict --home Brazil --away Argentina --historical
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import datetime, timezone

from .features import build_features_for_match, build_tournament_state
from .models import HistoricalModel, Prediction, TournamentModel
from .teams import resolve_team

DB_PATH = os.getenv("DB_PATH", "./copa.db")


def _render_prediction(p: Prediction) -> None:
    title = {
        "historical": "Modelo A - Historico",
        "tournament": "Modelo B - Apenas Copa 2026",
    }[p.model]
    rows = [
        ("Gols esperados (casa)", f"{p.expected_home:.2f}"),
        ("Gols esperados (visit.)", f"{p.expected_away:.2f}"),
        (
            "Placar mais provavel",
            f"{p.most_likely[0]} x {p.most_likely[1]} ({p.most_likely[2] * 100:.1f}%)",
        ),
        ("P(vitoria casa)", f"{p.p_home_win * 100:.1f}%"),
        ("P(empate)", f"{p.p_draw * 100:.1f}%"),
        ("P(vitoria visit.)", f"{p.p_away_win * 100:.1f}%"),
    ]
    if p.notes:
        rows.append(("Notas", p.notes))

    print(f"\n{title}")
    print("-" * len(title))
    width = max(len(label) for label, _ in rows)
    for label, value in rows:
        print(f"{label:<{width}}  {value}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Predict a WC2026 fixture.")
    parser.add_argument("--home", help="Home team name, code, or country")
    parser.add_argument("--away", help="Away team name, code, or country")
    parser.add_argument("--fixture-id", type=int, help="Predict a specific WC2026 fixture")
    parser.add_argument("--date", default=None, help="Match date (ISO). Defaults to now or fixture date")
    parser.add_argument(
        "--historical",
        action="store_true",
        help="Also run Modelo A. This loads pandas/statsmodels and can be slow in this environment.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    with sqlite3.connect(DB_PATH) as con:
        if args.fixture_id:
            row = con.execute(
                """SELECT home_team_id, away_team_id, date_utc
                   FROM fixtures WHERE id = ?""",
                (args.fixture_id,),
            ).fetchone()
            if not row:
                raise SystemExit(f"Fixture {args.fixture_id} not found")
            home_id, away_id, fixture_date = row
            date = args.date or fixture_date
        else:
            if not args.home or not args.away:
                raise SystemExit("Provide --home and --away, or --fixture-id")
            h = resolve_team(con, args.home)
            a = resolve_team(con, args.away)
            if not h:
                raise SystemExit(f"Home team '{args.home}' not found")
            if not a:
                raise SystemExit(f"Away team '{args.away}' not found")
            home_id, _, _ = h
            away_id, _, _ = a
            date = args.date or datetime.now(timezone.utc).isoformat()

        home_name = con.execute("SELECT name FROM teams WHERE id = ?", (home_id,)).fetchone()[0]
        away_name = con.execute("SELECT name FROM teams WHERE id = ?", (away_id,)).fetchone()[0]

    print(f"{home_name} x {away_name} ({date[:10]})")

    if args.historical:
        try:
            model_a = HistoricalModel.load()
            feats = build_features_for_match(home_id, away_id, date)
            _render_prediction(model_a.predict(feats))
        except FileNotFoundError:
            print("\nModelo A nao treinado. Rode `python -m src.models train-historical` primeiro.")

    state = build_tournament_state()
    if home_id not in state or away_id not in state:
        raise SystemExit("Modelo B exige times qualificados para a Copa 2026.")

    model_b = TournamentModel()
    _render_prediction(model_b.predict(state[home_id], state[away_id]))


if __name__ == "__main__":
    main()

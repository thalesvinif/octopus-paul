"""
FastAPI backend for the Copa Predictor 2026 UI.

Exposes the existing models and SQLite data as JSON. The default path uses
Modelo B (Tournament-only, fast, no pandas/statsmodels). Modelo A (Historical)
is loaded lazily, only when `?historical=true` is requested.

Run:
    uvicorn src.api:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from . import monitor
from .features import _team_form, build_tournament_state
from .ingest import refresh_world_cup_results
from .models import FeatureRow, Prediction, TournamentModel
from .teams import resolve_team

DB_PATH = os.getenv("DB_PATH", "./copa.db")
# How often the background job re-pulls results (seconds). 0 disables it.
REFRESH_INTERVAL_SECONDS = int(os.getenv("REFRESH_INTERVAL_SECONDS", "3600"))

logger = logging.getLogger("copa.refresh")

# Last refresh outcome, surfaced via GET /api/refresh.
_last_refresh: dict = {"status": "never", "at": None, "result": None, "error": None}


def _do_refresh() -> dict:
    """Run the football-data.org ingest and record the outcome."""
    try:
        result = refresh_world_cup_results()
        _last_refresh.update(
            status="ok",
            at=datetime.now(timezone.utc).isoformat(),
            result=result,
            error=None,
        )
        logger.info("WC2026 refresh ok: %s", result)
    except Exception as exc:  # noqa: BLE001
        _last_refresh.update(
            status="error",
            at=datetime.now(timezone.utc).isoformat(),
            error=str(exc),
        )
        logger.warning("WC2026 refresh failed: %s", exc)
    return _last_refresh


def _maybe_daily_snapshot() -> None:
    """Record one monitoring snapshot per day (after a refresh)."""
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        if not monitor.has_snapshot(today):
            monitor.snapshot(today=today)
            logger.info("monitor snapshot recorded for %s", today)
    except Exception as exc:  # noqa: BLE001
        logger.warning("monitor snapshot failed: %s", exc)


async def _refresh_loop() -> None:
    """Refresh once on boot, then every REFRESH_INTERVAL_SECONDS."""
    while True:
        await run_in_threadpool(_do_refresh)
        await run_in_threadpool(_maybe_daily_snapshot)
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = None
    if REFRESH_INTERVAL_SECONDS > 0:
        task = asyncio.create_task(_refresh_loop())
    try:
        yield
    finally:
        if task:
            task.cancel()


app = FastAPI(title="Copa Predictor 2026 API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # Any localhost/127.0.0.1 port in dev; override with CORS_ORIGINS in prod.
    allow_origins=os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else [],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _group_of(round_name: str | None) -> str | None:
    """'GROUP_A - Matchday 1' -> 'A'. Returns None for knockout/unknown rounds."""
    if not round_name or not round_name.upper().startswith("GROUP_"):
        return None
    return round_name.split(" - ")[0].replace("GROUP_", "").strip() or None


def _matchday_of(round_name: str | None) -> int | None:
    if not round_name or "Matchday" not in round_name:
        return None
    try:
        return int(round_name.rsplit("Matchday", 1)[1].strip())
    except ValueError:
        return None


def _team_brief(con: sqlite3.Connection, team_id: int) -> dict:
    row = con.execute(
        "SELECT id, name, code, country, flag_url FROM teams WHERE id = ?",
        (team_id,),
    ).fetchone()
    if not row:
        return {"id": team_id, "name": str(team_id), "code": None, "flag_url": None}
    return dict(row)


def _fixture_dict(con: sqlite3.Connection, row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "round": row["round"],
        "group": _group_of(row["round"]),
        "matchday": _matchday_of(row["round"]),
        "date_utc": row["date_utc"],
        "venue_city": row["venue_city"],
        "status": row["status"],
        "home": _team_brief(con, row["home_team_id"]),
        "away": _team_brief(con, row["away_team_id"]),
        "home_goals": row["home_goals"],
        "away_goals": row["away_goals"],
    }


def _prediction_dict(p: Prediction, home: dict, away: dict) -> dict:
    d = asdict(p)
    d["home"] = home
    d["away"] = away
    return d


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------
@app.get("/api/refresh")
def refresh_status() -> dict:
    """Last result-refresh outcome and the configured interval."""
    return {"interval_seconds": REFRESH_INTERVAL_SECONDS, **_last_refresh}


@app.post("/api/refresh")
async def refresh_now() -> dict:
    """Manually re-pull WC2026 results from football-data.org."""
    result = await run_in_threadpool(_do_refresh)
    if result["status"] == "error":
        raise HTTPException(502, f"Refresh falhou: {result['error']}")
    return {"interval_seconds": REFRESH_INTERVAL_SECONDS, **result}


@app.get("/api/monitor/history")
def monitor_history() -> dict:
    """Daily backtest snapshots + the recalibration trigger status."""
    history = monitor.read_history()
    return {
        "history": history,
        "latest": history[-1] if history else None,
        "recalibration": monitor.recalibration_status(history),
    }


@app.post("/api/monitor/run")
async def monitor_run() -> dict:
    """Run the backtest now and store today's snapshot."""
    await run_in_threadpool(monitor.snapshot)
    history = monitor.read_history()
    return {
        "history": history,
        "latest": history[-1] if history else None,
        "recalibration": monitor.recalibration_status(history),
    }


@app.get("/api/teams")
def list_teams() -> list[dict]:
    with _connect() as con:
        rows = con.execute(
            """SELECT id, name, code, country, flag_url FROM teams
               WHERE is_wc2026 = 1 ORDER BY name"""
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/fixtures")
def list_fixtures(
    status: str | None = Query(None, description="FT, NS, ..."),
    group: str | None = Query(None, description="Group letter A-L"),
    matchday: int | None = Query(None),
) -> list[dict]:
    with _connect() as con:
        rows = con.execute(
            """SELECT id, round, date_utc, venue_city, status,
                      home_team_id, away_team_id, home_goals, away_goals
               FROM fixtures
               WHERE is_wc2026 = 1
               ORDER BY date_utc""",
        ).fetchall()
        fixtures = [_fixture_dict(con, r) for r in rows]
    if status:
        fixtures = [f for f in fixtures if f["status"] == status]
    if group:
        fixtures = [f for f in fixtures if f["group"] == group.upper()]
    if matchday is not None:
        fixtures = [f for f in fixtures if f["matchday"] == matchday]
    return fixtures


@app.get("/api/standings")
def standings() -> dict[str, list[dict]]:
    """Group standings (A-L) computed from finished WC2026 group matches."""
    with _connect() as con:
        rows = con.execute(
            """SELECT round, home_team_id, away_team_id, home_goals, away_goals
               FROM fixtures
               WHERE is_wc2026 = 1 AND status = 'FT'
                 AND home_goals IS NOT NULL""",
        ).fetchall()

        table: dict[str, dict[int, dict]] = {}

        def _slot(group: str, team_id: int) -> dict:
            g = table.setdefault(group, {})
            if team_id not in g:
                brief = _team_brief(con, team_id)
                g[team_id] = {
                    "team": brief, "played": 0, "won": 0, "drawn": 0, "lost": 0,
                    "gf": 0, "ga": 0, "gd": 0, "points": 0,
                }
            return g[team_id]

        for r in rows:
            group = _group_of(r["round"])
            if not group:
                continue
            hg, ag = r["home_goals"], r["away_goals"]
            h = _slot(group, r["home_team_id"])
            a = _slot(group, r["away_team_id"])
            for side, gf, ga in ((h, hg, ag), (a, ag, hg)):
                side["played"] += 1
                side["gf"] += gf
                side["ga"] += ga
                side["gd"] = side["gf"] - side["ga"]
            if hg > ag:
                h["won"] += 1; h["points"] += 3; a["lost"] += 1
            elif ag > hg:
                a["won"] += 1; a["points"] += 3; h["lost"] += 1
            else:
                h["drawn"] += 1; a["drawn"] += 1
                h["points"] += 1; a["points"] += 1

    return {
        group: sorted(
            teams.values(),
            key=lambda t: (-t["points"], -t["gd"], -t["gf"]),
        )
        for group, teams in sorted(table.items())
    }


@app.get("/api/teams/{team_id}")
def team_detail(team_id: int) -> dict:
    with _connect() as con:
        brief = con.execute(
            "SELECT id, name, code, country, flag_url FROM teams WHERE id = ?",
            (team_id,),
        ).fetchone()
        if not brief:
            raise HTTPException(404, f"Team {team_id} not found")
        brief = dict(brief)

        now = datetime.now(timezone.utc).isoformat()
        form_gf, form_ga = _team_form(con, team_id, now)

        matches = con.execute(
            """SELECT id, round, date_utc, venue_city, status,
                      home_team_id, away_team_id, home_goals, away_goals
               FROM fixtures
               WHERE is_wc2026 = 1
                 AND (home_team_id = ? OR away_team_id = ?)
               ORDER BY date_utc""",
            (team_id, team_id),
        ).fetchall()
        wc_matches = [_fixture_dict(con, m) for m in matches]

    state = build_tournament_state().get(team_id)
    return {
        "team": brief,
        "elo": state.prior_elo if state else None,
        "form_gf": round(form_gf, 2),
        "form_ga": round(form_ga, 2),
        "tournament": {
            "matches_played": state.matches_played if state else 0,
            "goals_scored": state.goals_scored_total if state else 0,
            "goals_conceded": state.goals_conceded_total if state else 0,
        },
        "matches": wc_matches,
    }


@app.get("/api/tournament-state")
def tournament_state() -> list[dict]:
    state = build_tournament_state()
    out = []
    for s in sorted(state.values(), key=lambda x: -x.matches_played):
        if s.matches_played == 0:
            continue
        out.append({
            "team_code": s.team_code,
            "matches_played": s.matches_played,
            "goals_scored": s.goals_scored_total,
            "goals_conceded": s.goals_conceded_total,
            "prior_elo": round(s.prior_elo, 0),
        })
    return out


@app.get("/api/predict")
def predict(
    home: str | None = None,
    away: str | None = None,
    fixture_id: int | None = None,
    historical: bool = False,
) -> dict:
    """Predict a matchup. Always returns Modelo B; adds Modelo A when historical=true."""
    with _connect() as con:
        if fixture_id:
            row = con.execute(
                """SELECT home_team_id, away_team_id, date_utc
                   FROM fixtures WHERE id = ?""",
                (fixture_id,),
            ).fetchone()
            if not row:
                raise HTTPException(404, f"Fixture {fixture_id} not found")
            home_id, away_id = row["home_team_id"], row["away_team_id"]
            date = row["date_utc"]
        else:
            if not home or not away:
                raise HTTPException(400, "Provide home & away, or fixture_id")
            h = resolve_team(con, home)
            a = resolve_team(con, away)
            if not h:
                raise HTTPException(404, f"Home team '{home}' not found")
            if not a:
                raise HTTPException(404, f"Away team '{away}' not found")
            home_id, away_id = h[0], a[0]
            date = datetime.now(timezone.utc).isoformat()

        home_brief = _team_brief(con, home_id)
        away_brief = _team_brief(con, away_id)

    predictions: list[dict] = []

    # Modelo A — opt-in, loads statsmodels lazily.
    if historical:
        try:
            from .features import build_features_for_match
            from .models import HistoricalModel

            model_a = HistoricalModel.load()
            feats = build_features_for_match(home_id, away_id, date)
            pred_a = model_a.predict(feats)
            pred_a.features = [
                FeatureRow("Elo", round(feats.home_elo), round(feats.away_elo)),
                FeatureRow(
                    "Forma — gols marcados (últ. 10)",
                    round(feats.home_form_gf, 2), round(feats.away_form_gf, 2),
                ),
                FeatureRow(
                    "Forma — gols sofridos (últ. 10)",
                    round(feats.home_form_ga, 2), round(feats.away_form_ga, 2),
                ),
                FeatureRow(
                    "Aproveitamento no H2H (mandante)",
                    f"{round(feats.h2h_home_winrate * 100)}%", None,
                ),
                FeatureRow(
                    "Descanso (dias)",
                    round(feats.home_rest_days), round(feats.away_rest_days),
                ),
            ]
            predictions.append(_prediction_dict(pred_a, home_brief, away_brief))
        except FileNotFoundError:
            raise HTTPException(
                503,
                "Modelo A nao treinado. Rode `python -m src.models train-historical`.",
            )

    # Modelo B — default, fast.
    state = build_tournament_state()
    if home_id not in state or away_id not in state:
        raise HTTPException(422, "Modelo B exige times qualificados para a Copa 2026.")
    model_b = TournamentModel()
    predictions.append(
        _prediction_dict(model_b.predict(state[home_id], state[away_id]), home_brief, away_brief)
    )

    return {
        "home": home_brief,
        "away": away_brief,
        "date_utc": date,
        "predictions": predictions,
    }

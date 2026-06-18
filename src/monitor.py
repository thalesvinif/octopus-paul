"""
Model monitoring: backtest metrics over the finished WC2026 matches, a daily
CSV snapshot log, and an objective trigger that flags when recalibration is
worth a human review.

Nothing here changes the model. It only observes and reports.
"""
from __future__ import annotations

import csv
import math
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .elo_loader import all_latest_elo
from .features import build_features_for_match, build_training_set
from .models import HistoricalModel, TournamentModel, TournamentTeamState

DB_PATH = os.getenv("DB_PATH", "./copa.db")
METRICS_LOG = Path(os.getenv("METRICS_LOG", "./metrics_log.csv"))

# --- Recalibration trigger thresholds (human decides; this only flags) --------
RECAL_MIN_GAMES = 72        # ~end of the group stage: enough sample to judge
RECAL_Z = 2.0               # draw-rate deviation significance (|z| >= 2)
RECAL_PERSIST_DAYS = 5      # the deviation must hold this many snapshots in a row

CSV_FIELDS = [
    "date", "n_games", "draw_rate_real",
    "A_acc", "A_rps", "A_brier", "A_logloss", "A_draw_pred",
    "B_acc", "B_rps", "B_brier", "B_logloss", "B_draw_pred",
    "base_rps", "base_brier",
]
_INT_FIELDS = {"n_games"}


# ----------------------------------------------------------------------
# Backtest
# ----------------------------------------------------------------------
def _outcome(h: int, a: int) -> str:
    return "H" if h > a else ("A" if a > h else "D")


def _state_before(con, tid, code, date, prior) -> TournamentTeamState:
    rows = con.execute(
        """SELECT home_team_id, home_goals, away_goals FROM fixtures
           WHERE is_wc2026=1 AND status='FT' AND home_goals IS NOT NULL
             AND date_utc < ? AND (home_team_id=? OR away_team_id=?)""",
        (date, tid, tid),
    ).fetchall()
    gs = gc = 0
    for h, hg, ag in rows:
        if h == tid:
            gs += hg; gc += ag
        else:
            gs += ag; gc += hg
    return TournamentTeamState(
        team_id=tid, team_code=code or "", matches_played=len(rows),
        goals_scored_total=gs, goals_conceded_total=gc,
        prior_elo=prior.get(code or "", 1500),
    )


def run_backtest(db_path: str = DB_PATH) -> dict:
    """Leak-free backtest over all finished WC2026 matches.

    Modelo A is retrained excluding WC2026; Modelo B uses point-in-time state.
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    prior = all_latest_elo(on_or_before="2026-06-10")

    model_a = HistoricalModel()
    model_a.fit(build_training_set(exclude_wc2026=True))
    model_b = TournamentModel()

    def code(tid):
        r = con.execute("SELECT code FROM teams WHERE id=?", (tid,)).fetchone()
        return r[0] if r else str(tid)

    matches = con.execute(
        """SELECT date_utc, home_team_id, away_team_id, home_goals, away_goals
           FROM fixtures
           WHERE is_wc2026=1 AND status='FT' AND home_goals IS NOT NULL
           ORDER BY date_utc"""
    ).fetchall()
    n = len(matches)

    agg = {m: {"acc": 0, "brier": 0.0, "rps": 0.0, "ll": 0.0, "draw_pred": 0.0}
           for m in ("A", "B")}
    base = {"brier": 0.0, "rps": 0.0}
    draws_real = 0

    for m in matches:
        hid, aid = m["home_team_id"], m["away_team_id"]
        hg, ag = m["home_goals"], m["away_goals"]
        real = _outcome(hg, ag)
        draws_real += real == "D"

        pa = model_a.predict(build_features_for_match(hid, aid, m["date_utc"]))
        pb = model_b.predict(
            _state_before(con, hid, code(hid), m["date_utc"], prior),
            _state_before(con, aid, code(aid), m["date_utc"], prior),
        )
        for tag, p in (("A", pa), ("B", pb)):
            pr = {"H": p.p_home_win, "D": p.p_draw, "A": p.p_away_win}
            agg[tag]["draw_pred"] += pr["D"]
            if max(pr, key=pr.get) == real:
                agg[tag]["acc"] += 1
            agg[tag]["brier"] += sum((pr[k] - (1.0 if k == real else 0.0)) ** 2 for k in "HDA")
            cp = co = 0.0
            for k in ("H", "D"):
                cp += pr[k]; co += 1.0 if real == k else 0.0; agg[tag]["rps"] += (cp - co) ** 2
            agg[tag]["ll"] += -math.log(max(pr[real], 1e-12))

        b = {"H": 1 / 3, "D": 1 / 3, "A": 1 / 3}
        base["brier"] += sum((b[k] - (1.0 if k == real else 0.0)) ** 2 for k in "HDA")
        cp = co = 0.0
        for k in ("H", "D"):
            cp += b[k]; co += 1.0 if real == k else 0.0; base["rps"] += (cp - co) ** 2

    con.close()
    if n == 0:
        return {"n_games": 0, "draw_rate_real": 0.0,
                "A": None, "B": None, "baseline": None}

    out: dict = {"n_games": n, "draw_rate_real": draws_real / n}
    for tag in ("A", "B"):
        out[tag] = {
            "acc": agg[tag]["acc"] / n,
            "brier": agg[tag]["brier"] / n,
            "rps": agg[tag]["rps"] / n / 2,
            "logloss": agg[tag]["ll"] / n,
            "draw_pred": agg[tag]["draw_pred"] / n,
        }
    out["baseline"] = {"brier": base["brier"] / n, "rps": base["rps"] / n / 2}
    return out


# ----------------------------------------------------------------------
# CSV snapshot log
# ----------------------------------------------------------------------
def read_history() -> list[dict]:
    """Return the snapshot log with numeric fields parsed."""
    if not METRICS_LOG.exists():
        return []
    rows: list[dict] = []
    with open(METRICS_LOG, newline="") as f:
        for raw in csv.DictReader(f):
            row: dict = {}
            for k, v in raw.items():
                if k == "date":
                    row[k] = v
                elif k in _INT_FIELDS:
                    row[k] = int(float(v)) if v not in ("", None) else 0
                else:
                    row[k] = float(v) if v not in ("", None) else 0.0
            rows.append(row)
    return rows


def _flat_row(date: str, r: dict) -> dict:
    def g(m, k):
        return round((r[m] or {}).get(k, 0.0), 4) if r.get(m) else 0.0
    return {
        "date": date,
        "n_games": r["n_games"],
        "draw_rate_real": round(r["draw_rate_real"], 4),
        "A_acc": g("A", "acc"), "A_rps": g("A", "rps"), "A_brier": g("A", "brier"),
        "A_logloss": g("A", "logloss"), "A_draw_pred": g("A", "draw_pred"),
        "B_acc": g("B", "acc"), "B_rps": g("B", "rps"), "B_brier": g("B", "brier"),
        "B_logloss": g("B", "logloss"), "B_draw_pred": g("B", "draw_pred"),
        "base_rps": g("baseline", "rps"), "base_brier": g("baseline", "brier"),
    }


def snapshot(db_path: str = DB_PATH, today: str | None = None) -> dict:
    """Run the backtest and upsert today's row in the CSV log. Returns metrics."""
    r = run_backtest(db_path)
    date = today or datetime.now(timezone.utc).date().isoformat()
    row = _flat_row(date, r)

    history = read_history()
    history = [h for h in history if h["date"] != date]
    history.append(row)
    history.sort(key=lambda h: h["date"])

    with open(METRICS_LOG, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for h in history:
            w.writerow({k: h.get(k, "") for k in CSV_FIELDS})
    return r


def has_snapshot(date: str) -> bool:
    return any(h["date"] == date for h in read_history())


# ----------------------------------------------------------------------
# Recalibration trigger
# ----------------------------------------------------------------------
def _z(p_obs: float, p_exp: float, n: int) -> float:
    if n <= 0 or p_exp <= 0 or p_exp >= 1:
        return 0.0
    return (p_obs - p_exp) / math.sqrt(p_exp * (1 - p_exp) / n)


def recalibration_status(history: list[dict] | None = None) -> dict:
    """Flag whether recalibration is worth a human review. Never acts."""
    history = history if history is not None else read_history()
    empty = {
        "state": "green", "recommend": False, "eligible": False,
        "n_games": 0, "min_games": RECAL_MIN_GAMES, "draw_real": 0.0,
        "draw_pred": 0.0, "z": 0.0, "days_persistent": 0,
        "persist_days": RECAL_PERSIST_DAYS,
        "reason": "Sem dados ainda — rode o backtest.",
    }
    if not history:
        return empty

    latest = history[-1]
    n = int(latest["n_games"])
    draw_real = latest["draw_rate_real"]
    draw_pred = latest["A_draw_pred"]  # expected draw rate per Modelo A
    z = _z(draw_real, draw_pred, n)
    eligible = n >= RECAL_MIN_GAMES
    significant = abs(z) >= RECAL_Z

    # trailing run of significant snapshots
    days_persistent = 0
    for h in reversed(history):
        if abs(_z(h["draw_rate_real"], h["A_draw_pred"], int(h["n_games"]))) >= RECAL_Z:
            days_persistent += 1
        else:
            break
    persistent = days_persistent >= RECAL_PERSIST_DAYS
    recommend = eligible and persistent

    if recommend:
        state = "red"
        reason = (
            f"Reconsiderar calibração: {n} jogos e desvio de empate persistente "
            f"(z={z:+.1f} por {days_persistent} dias). Decisão humana — refazer a "
            f"calibração out-of-sample incluindo os jogos acumulados."
        )
    elif significant and not eligible:
        state = "yellow"
        reason = (
            f"De olho: desvio de empate significativo (z={z:+.1f}), mas só "
            f"{n}/{RECAL_MIN_GAMES} jogos. Aguardar mais amostra."
        )
    elif significant and eligible and not persistent:
        state = "yellow"
        reason = (
            f"De olho: desvio significativo (z={z:+.1f}) há {days_persistent} de "
            f"{RECAL_PERSIST_DAYS} dias necessários. Aguardar persistência."
        )
    elif not eligible:
        state = "green"
        reason = (
            f"Sem gatilho: amostra insuficiente ({n}/{RECAL_MIN_GAMES} jogos). "
            f"Desvio de empate atual z={z:+.1f}."
        )
    else:
        state = "green"
        reason = (
            f"Sem gatilho: {n} jogos, desvio de empate dentro do ruído "
            f"(z={z:+.1f})."
        )

    return {
        "state": state, "recommend": recommend, "eligible": eligible,
        "n_games": n, "min_games": RECAL_MIN_GAMES,
        "draw_real": round(draw_real, 4), "draw_pred": round(draw_pred, 4),
        "z": round(z, 2), "days_persistent": days_persistent,
        "persist_days": RECAL_PERSIST_DAYS, "reason": reason,
    }


if __name__ == "__main__":
    r = snapshot()
    print(f"snapshot gravado: {r['n_games']} jogos")
    print(recalibration_status()["reason"])

"""
Backtest: roda Modelo A e Modelo B em todos os jogos JÁ ENCERRADOS da Copa 2026
e compara com o resultado real.

Anti-vazamento:
  - Modelo A: features de forma/H2H/descanso usam só jogos com data < data do jogo.
  - Modelo B: estado do torneio reconstruído com corte na data do jogo (só partidas
    da Copa anteriores).

Métricas: acerto de resultado (1X2), acerto do placar exato, Brier (3 classes),
RPS (ordenado) e log-loss.
"""
from __future__ import annotations

import math
import sqlite3

from src.elo_loader import all_latest_elo
from src.features import build_features_for_match, build_training_set
from src.models import HistoricalModel, TournamentModel, TournamentTeamState

DB = "./copa.db"


def outcome(hg: int, ag: int) -> str:
    return "H" if hg > ag else ("A" if ag > hg else "D")


def state_before(con, tid, code, date, prior_elo) -> TournamentTeamState:
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
        prior_elo=prior_elo.get(code or "", 1500),
    )


def brier(probs: dict, actual: str) -> float:
    return sum((probs[k] - (1.0 if k == actual else 0.0)) ** 2 for k in "HDA")


def rps(probs: dict, actual: str) -> float:
    # ordem H, D, A
    order = ["H", "D", "A"]
    cum_p = cum_o = 0.0
    s = 0.0
    for k in order[:-1]:
        cum_p += probs[k]
        cum_o += 1.0 if k == actual else 0.0
        s += (cum_p - cum_o) ** 2
    return s / (len(order) - 1)


def logloss(probs: dict, actual: str) -> float:
    return -math.log(max(probs[actual], 1e-12))


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    prior_elo = all_latest_elo(on_or_before="2026-06-10")
    # Leak-free Modelo A: trained WITHOUT the WC2026 matches we are testing on.
    print("Treinando Modelo A sem os jogos da Copa 2026 (anti-vazamento)...")
    model_a = HistoricalModel()
    model_a.fit(build_training_set(exclude_wc2026=True))
    model_b = TournamentModel()

    matches = con.execute(
        """SELECT id, date_utc, home_team_id, away_team_id, home_goals, away_goals
           FROM fixtures
           WHERE is_wc2026=1 AND status='FT' AND home_goals IS NOT NULL
           ORDER BY date_utc"""
    ).fetchall()

    def code(tid):
        r = con.execute("SELECT code FROM teams WHERE id=?", (tid,)).fetchone()
        return r[0] if r else str(tid)

    agg = {m: {"acc": 0, "exact": 0, "brier": 0.0, "rps": 0.0, "ll": 0.0}
           for m in ("A", "B")}
    n = len(matches)
    print(f"Backtest em {n} jogos encerrados da Copa 2026\n")
    header = f"{'jogo':<11} {'real':>5} | {'A pred':>7} {'A 1X2':>5} {'A✓':>2} | {'B pred':>7} {'B 1X2':>5} {'B✓':>2}"
    print(header)
    print("-" * len(header))

    for m in matches:
        hid, aid = m["home_team_id"], m["away_team_id"]
        hg, ag = m["home_goals"], m["away_goals"]
        real = outcome(hg, ag)
        hc, ac = code(hid), code(aid)

        # Modelo A
        feats = build_features_for_match(hid, aid, m["date_utc"])
        pa = model_a.predict(feats)
        # Modelo B (point-in-time)
        sh = state_before(con, hid, hc, m["date_utc"], prior_elo)
        sa = state_before(con, aid, ac, m["date_utc"], prior_elo)
        pb = model_b.predict(sh, sa)

        line = f"{hc}-{ac:<6} {hg}-{ag:>3} |"
        for tag, p in (("A", pa), ("B", pb)):
            probs = {"H": p.p_home_win, "D": p.p_draw, "A": p.p_away_win}
            pred = max(probs, key=probs.get)
            ml = p.most_likely
            ok = pred == real
            exact = (ml[0] == hg and ml[1] == ag)
            agg[tag]["acc"] += ok
            agg[tag]["exact"] += exact
            agg[tag]["brier"] += brier(probs, real)
            agg[tag]["rps"] += rps(probs, real)
            agg[tag]["ll"] += logloss(probs, real)
            line += f" {ml[0]}-{ml[1]:<5} {pred:>5} {'✓' if ok else '·':>2} |"
        print(line)

    print("\n=== AGREGADO (médias; ↓ melhor p/ Brier, RPS, log-loss) ===")
    print(f"{'métrica':<22} {'Modelo A':>10} {'Modelo B':>10}")
    print(f"{'acerto 1X2':<22} {agg['A']['acc']/n:>9.1%} {agg['B']['acc']/n:>10.1%}")
    print(f"{'acerto placar exato':<22} {agg['A']['exact']/n:>9.1%} {agg['B']['exact']/n:>10.1%}")
    print(f"{'Brier (3 classes)':<22} {agg['A']['brier']/n:>10.3f} {agg['B']['brier']/n:>10.3f}")
    print(f"{'RPS':<22} {agg['A']['rps']/n:>10.3f} {agg['B']['rps']/n:>10.3f}")
    print(f"{'log-loss':<22} {agg['A']['ll']/n:>10.3f} {agg['B']['ll']/n:>10.3f}")

    # baseline: chute 1/3 cada
    base = {"H": 1/3, "D": 1/3, "A": 1/3}
    bb = sum(brier(base, outcome(m["home_goals"], m["away_goals"])) for m in matches) / n
    br = sum(rps(base, outcome(m["home_goals"], m["away_goals"])) for m in matches) / n
    bl = sum(logloss(base, outcome(m["home_goals"], m["away_goals"])) for m in matches) / n
    print(f"{'baseline (1/3 cada)':<22} {'—':>10} {'':>4}  Brier={bb:.3f} RPS={br:.3f} LL={bl:.3f}")


if __name__ == "__main__":
    main()

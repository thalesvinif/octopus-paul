"""
Prediction models.

Both models output a goal distribution (matrix of P(home=i, away=j) for i,j in 0..6)
and reduce it to:
  - expected goals for each side
  - probabilities of home win / draw / away win
  - the single most likely scoreline

Modelo A (Histórico):
    Poisson regression on historical features (Elo, form, H2H, rest).
    Trained on all international matches in `fixtures` since 2020.

Modelo B (Tournament-only):
    Bayesian gamma-Poisson update. Prior derived from pre-tournament Elo,
    posterior updated using only WC2026 finished matches.
"""
from __future__ import annotations

import os
import pickle
import sqlite3
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .features import (
    MatchFeatures,
    TournamentTeamState,
    build_tournament_state,
)

DB_PATH = os.getenv("DB_PATH", "./copa.db")
MODEL_PATH = Path("./models_artifacts")
MODEL_PATH.mkdir(exist_ok=True)
MAX_GOALS = 7  # truncate score matrix at 7-7

# Draw inflation knob: multiplies every i-i scoreline before renormalizing.
# Left OFF (1.0). Out-of-sample calibration on ~800 real internationals
# (2020-25, temporal 80/20 split) showed the independent Poisson already nails
# the draw rate — it predicted 21.3% draws vs 20.6% observed — and every score
# (Brier/RPS/log-loss) was best at 1.0 and got worse as the boost rose. The 39%
# draw rate in the first 23 WC2026 games was small-sample noise; tuning to it
# overfits. The knob stays here to re-test if a real, larger draw skew shows up.
#
# Experiment (NOT applied): fitting scale+boost purely to those 23 WC games
# maxes out at 11/23 correct (vs 10/23 at 1.0), and only by halving expected
# goals (scale ~0.5) + boost 1.2 (Modelo A) / 1.8 (Modelo B) — a clear overfit
# that would generalize worse. Kept at 1.0 by choice.
DRAW_BOOST = 1.0


# ======================================================================
# Shared utilities
# ======================================================================
@dataclass
class FeatureRow:
    """One input value shown for transparency. `away` is None for single values."""
    label: str
    home: float | str | None
    away: float | str | None = None


@dataclass
class Prediction:
    model: Literal["historical", "tournament"]
    expected_home: float
    expected_away: float
    p_home_win: float
    p_draw: float
    p_away_win: float
    most_likely: tuple[int, int, float]
    score_matrix: list[list[float]]
    notes: str = ""
    features: list[FeatureRow] | None = None


def _poisson_pmf(lam: float, max_goals: int = MAX_GOALS) -> list[float]:
    values = []
    for goals in range(max_goals + 1):
        values.append(math.exp(-lam) * (lam ** goals) / math.factorial(goals))
    return values


def _dc_tau(x: int, y: int, lam: float, mu: float, rho: float) -> float:
    """Dixon-Coles low-score correction factor τ(x, y).

    With rho < 0 this lifts 0-0 and 1-1 and damps 1-0 / 0-1, fixing the
    independent-Poisson under-prediction of low-scoring draws. Scores with
    x >= 2 or y >= 2 are left untouched (τ = 1).
    """
    if x == 0 and y == 0:
        return 1.0 - lam * mu * rho
    if x == 0 and y == 1:
        return 1.0 + lam * rho
    if x == 1 and y == 0:
        return 1.0 + mu * rho
    if x == 1 and y == 1:
        return 1.0 - rho
    return 1.0


def _poisson_matrix(
    lambda_home: float,
    lambda_away: float,
    rho: float = 0.0,
    draw_boost: float = 1.0,
) -> list[list[float]]:
    """Bivariate Poisson score matrix with optional corrections.

    rho = 0 and draw_boost = 1 reduce to the independent outer product of two
    Poisson PMFs. rho applies the Dixon-Coles low-score factor; draw_boost
    scales every i-i scoreline to lift the overall draw probability.
    """
    home_probs = _poisson_pmf(lambda_home)
    away_probs = _poisson_pmf(lambda_away)
    matrix = [[h * a for a in away_probs] for h in home_probs]
    if rho:
        for i in (0, 1):
            for j in (0, 1):
                tau = _dc_tau(i, j, lambda_home, lambda_away, rho)
                # Guard against negative cells for extreme rho/lambda combos.
                matrix[i][j] *= max(tau, 0.0)
    if draw_boost != 1.0:
        for i in range(len(matrix)):
            matrix[i][i] *= draw_boost
    total = sum(sum(row) for row in matrix)
    return [[cell / total for cell in row] for row in matrix]


def _matrix_to_prediction(
    model: str,
    m: list[list[float]],
    lam_h: float,
    lam_a: float,
    notes: str = "",
    score_matrix: list[list[float]] | None = None,
) -> Prediction:
    """Build a Prediction.

    W/D/L probabilities come from `m` (the draw-calibrated matrix). The single
    most-likely scoreline and the displayed score grid come from `score_matrix`
    when given (the raw, un-boosted distribution) so the headline scoreline keeps
    its variety instead of collapsing onto 1-1. Falls back to `m` when omitted.
    """
    sm = score_matrix if score_matrix is not None else m
    home_win = away_win = draw = 0.0
    for i, row in enumerate(m):
        for j, prob in enumerate(row):
            if i > j:
                home_win += prob
            elif j > i:
                away_win += prob
            else:
                draw += prob
    best = (0, 0, -1.0)
    for i, row in enumerate(sm):
        for j, prob in enumerate(row):
            if prob > best[2]:
                best = (i, j, prob)
    return Prediction(
        model=model,  # type: ignore
        expected_home=lam_h,
        expected_away=lam_a,
        p_home_win=home_win,
        p_draw=draw,
        p_away_win=away_win,
        most_likely=best,
        score_matrix=sm,
        notes=notes,
    )


# ======================================================================
# Modelo A — Historical Poisson regression
# ======================================================================
HOME_FEATURES = [
    "elo_diff",
    "home_form_gf",
    "away_form_ga",
    "h2h_home_winrate",
    "home_rest",
]
AWAY_FEATURES = [
    "elo_diff",          # sign flips during construction
    "away_form_gf",
    "home_form_ga",
    "h2h_home_winrate",
    "away_rest",
]


def estimate_rho(
    lams_h: list[float], lams_a: list[float], xs: list[int], ys: list[int]
) -> float:
    """1-D MLE of the Dixon-Coles rho on low-scoring training matches.

    Only scores with both teams <= 1 carry information (τ = 1 elsewhere),
    so the Poisson term drops out and we maximize Σ log τ over rho alone.
    """
    from scipy.optimize import minimize_scalar

    def nll(rho: float) -> float:
        s = 0.0
        for lam, mu, x, y in zip(lams_h, lams_a, xs, ys):
            if x <= 1 and y <= 1:
                t = _dc_tau(int(x), int(y), lam, mu, rho)
                if t <= 1e-9:
                    return 1e12
                s += math.log(t)
        return -s

    res = minimize_scalar(nll, bounds=(-0.3, 0.3), method="bounded")
    return float(res.x)


class HistoricalModel:
    """Two independent Poisson GLMs (home/away goals) + Dixon-Coles rho.

    Predictions are made venue-neutral by averaging both team orderings,
    since the World Cup is played on neutral ground.
    """

    def __init__(self):
        self.model_home: Any | None = None
        self.model_away: Any | None = None
        self.rho: float = 0.0

    def fit(self, df) -> None:
        import statsmodels.api as sm

        X_h = sm.add_constant(df[HOME_FEATURES])
        X_a = sm.add_constant(df[AWAY_FEATURES])
        self.model_home = sm.GLM(df["home_goals"], X_h, family=sm.families.Poisson()).fit()
        self.model_away = sm.GLM(df["away_goals"], X_a, family=sm.families.Poisson()).fit()
        # Dixon-Coles rho is left at 0 (independent Poisson). Estimating it on
        # this data (estimate_rho, 822 internationals 2020-25) yields rho ~ +0.03,
        # but the low-score cells deviate < 1σ from independence — i.e. not
        # significant. For national teams the independent Poisson is already well
        # calibrated, so we don't carry a parameter that fails a significance test.
        # The DC machinery (estimate_rho, _dc_tau, _poisson_matrix's rho arg) stays
        # available to re-check if the dataset grows.
        self.rho = 0.0

    @staticmethod
    def _swap(f: MatchFeatures) -> MatchFeatures:
        """Mirror a feature row so the two teams trade places."""
        from dataclasses import replace

        return replace(
            f,
            home_team_id=f.away_team_id,
            away_team_id=f.home_team_id,
            home_elo=f.away_elo,
            away_elo=f.home_elo,
            elo_diff=-f.elo_diff,
            home_form_gf=f.away_form_gf,
            home_form_ga=f.away_form_ga,
            away_form_gf=f.home_form_gf,
            away_form_ga=f.home_form_ga,
            h2h_home_winrate=1.0 - f.h2h_home_winrate,
            home_rest_days=f.away_rest_days,
            away_rest_days=f.home_rest_days,
        )

    def predict_lambdas(self, f: MatchFeatures) -> tuple[float, float]:
        import pandas as pd

        if self.model_home is None or self.model_away is None:
            raise RuntimeError("Call fit() or load() first")
        x_h = pd.DataFrame([{
            "const": 1.0,
            "elo_diff": f.elo_diff,
            "home_form_gf": f.home_form_gf,
            "away_form_ga": f.away_form_ga,
            "h2h_home_winrate": f.h2h_home_winrate,
            "home_rest": f.home_rest_days,
        }])
        x_a = pd.DataFrame([{
            "const": 1.0,
            "elo_diff": f.elo_diff,
            "away_form_gf": f.away_form_gf,
            "home_form_ga": f.home_form_ga,
            "h2h_home_winrate": f.h2h_home_winrate,
            "away_rest": f.away_rest_days,
        }])
        return (
            float(self.model_home.predict(x_h).iloc[0]),
            float(self.model_away.predict(x_a).iloc[0]),
        )

    def predict(self, f: MatchFeatures) -> Prediction:
        # Venue-neutral: average each side's goals across both orderings.
        lam_h1, lam_a1 = self.predict_lambdas(f)
        lam_h2, lam_a2 = self.predict_lambdas(self._swap(f))
        lam_h = 0.5 * (lam_h1 + lam_a2)
        lam_a = 0.5 * (lam_a1 + lam_h2)
        m_prob = _poisson_matrix(lam_h, lam_a, self.rho, DRAW_BOOST)
        m_score = _poisson_matrix(lam_h, lam_a, self.rho, 1.0)
        return _matrix_to_prediction(
            "historical", m_prob, lam_h, lam_a, score_matrix=m_score
        )

    def save(self, path: Path = MODEL_PATH / "historical.pkl") -> None:
        with open(path, "wb") as f:
            pickle.dump(
                {"home": self.model_home, "away": self.model_away, "rho": self.rho},
                f,
            )

    @classmethod
    def load(cls, path: Path = MODEL_PATH / "historical.pkl") -> "HistoricalModel":
        with open(path, "rb") as f:
            obj = pickle.load(f)
        m = cls()
        m.model_home = obj["home"]
        m.model_away = obj["away"]
        m.rho = obj.get("rho", 0.0)
        return m


# ======================================================================
# Modelo B — Tournament-only Bayesian Gamma-Poisson
# ======================================================================
@dataclass
class BayesianPriorConfig:
    """How aggressively to anchor to the pre-tournament Elo prior.

    Higher prior_strength = slower to be swayed by tournament data.
    With prior_strength = 3 (matches), after 3 group games the posterior
    is roughly 50/50 prior vs data.
    """
    prior_strength: float = 3.0           # equivalent pseudo-matches
    elo_baseline: float = 1500.0
    elo_scale: float = 400.0              # 400-Elo gap = 10x scoring ratio
    tournament_avg_goals: float = 1.35    # WC mean goals/team historically
    rho: float = 0.0                      # Dixon-Coles off: not significant for NTs
    draw_boost: float = DRAW_BOOST        # diagonal draw inflation (see DRAW_BOOST)


class TournamentModel:
    """Bayesian gamma-Poisson model anchored on pre-tournament Elo."""

    def __init__(self, config: BayesianPriorConfig | None = None):
        self.config = config or BayesianPriorConfig()

    def _team_lambdas(self, st: TournamentTeamState) -> tuple[float, float]:
        """Return (posterior_attack, posterior_defense) for a team."""
        c = self.config
        # Prior centered on tournament avg, shifted by Elo
        # Stronger teams: higher prior attack, lower prior defense
        elo_factor = 10 ** ((st.prior_elo - c.elo_baseline) / c.elo_scale)
        prior_attack = c.tournament_avg_goals * elo_factor ** 0.5
        prior_defense = c.tournament_avg_goals / (elo_factor ** 0.5)

        # Gamma(α, β) prior on rate with mean α/β = prior_*
        # We use β = prior_strength (pseudo-matches), so α = mean × β
        beta = c.prior_strength
        alpha_atk = prior_attack * beta
        alpha_def = prior_defense * beta

        n = st.matches_played
        # Posterior: Gamma(α + total_goals, β + n)
        post_atk = (alpha_atk + st.goals_scored_total) / (beta + n)
        post_def = (alpha_def + st.goals_conceded_total) / (beta + n)
        return post_atk, post_def

    def predict(
        self,
        home: TournamentTeamState,
        away: TournamentTeamState,
        home_advantage: float = 1.0,    # neutral venue
    ) -> Prediction:
        h_atk, h_def = self._team_lambdas(home)
        a_atk, a_def = self._team_lambdas(away)

        # Expected goals: own attack × opponent defense ratio, normalized by tournament mean
        avg = self.config.tournament_avg_goals
        lam_h = (h_atk * a_def / avg) * home_advantage
        lam_a = (a_atk * h_def / avg)

        m_prob = _poisson_matrix(lam_h, lam_a, self.config.rho, self.config.draw_boost)
        m_score = _poisson_matrix(lam_h, lam_a, self.config.rho, 1.0)
        notes = (
            f"baseado em {home.matches_played} jogos do {home.team_code} "
            f"e {away.matches_played} do {away.team_code} na Copa 2026"
        )
        features = [
            FeatureRow("Elo pré-Copa", round(home.prior_elo), round(away.prior_elo)),
            FeatureRow("Jogos na Copa", home.matches_played, away.matches_played),
            FeatureRow(
                "Gols marcados (Copa)",
                home.goals_scored_total, away.goals_scored_total,
            ),
            FeatureRow(
                "Gols sofridos (Copa)",
                home.goals_conceded_total, away.goals_conceded_total,
            ),
            FeatureRow("Ataque estimado", round(h_atk, 2), round(a_atk, 2)),
            FeatureRow("Defesa estimada", round(h_def, 2), round(a_def, 2)),
        ]
        pred = _matrix_to_prediction(
            "tournament", m_prob, lam_h, lam_a, notes, score_matrix=m_score
        )
        pred.features = features
        return pred


# ======================================================================
# CLI: train / inspect
# ======================================================================
def train_historical(since: str = "2020-01-01"):
    """Train Modelo A on historical international matches."""
    from .features import build_training_set

    print("Building training set...")
    df = build_training_set(since=since)
    print(f"  {len(df)} matches")
    print("Fitting Poisson GLMs...")
    m = HistoricalModel()
    m.fit(df)
    m.save()
    print("Saved to models_artifacts/historical.pkl")
    print("\nHome goals model summary:")
    print(m.model_home.summary().tables[1])


def inspect_tournament():
    """Print current tournament state per team."""
    state = build_tournament_state()
    for s in sorted(state.values(), key=lambda x: -x.matches_played):
        if s.matches_played == 0:
            continue
        print(
            f"{s.team_code:>3} | played={s.matches_played} "
            f"GF={s.goals_scored_total} GA={s.goals_conceded_total} "
            f"prior_elo={s.prior_elo:.0f}"
        )


def cli():
    import argparse

    parser = argparse.ArgumentParser(description="Model training and inspection.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    train_parser = subparsers.add_parser("train-historical")
    train_parser.add_argument("--since", default="2020-01-01")
    subparsers.add_parser("inspect-tournament")
    args = parser.parse_args()

    if args.command == "train-historical":
        train_historical(since=args.since)
    elif args.command == "inspect-tournament":
        inspect_tournament()


if __name__ == "__main__":
    cli()

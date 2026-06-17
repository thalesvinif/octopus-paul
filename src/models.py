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
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import click
import numpy as np
import pandas as pd
import statsmodels.api as sm

from .features import (
    MatchFeatures,
    TournamentTeamState,
    build_features_for_match,
    build_tournament_state,
    build_training_set,
)
from .elo_loader import latest_elo

DB_PATH = os.getenv("DB_PATH", "./copa.db")
MODEL_PATH = Path("./models_artifacts")
MODEL_PATH.mkdir(exist_ok=True)
MAX_GOALS = 7  # truncate score matrix at 7-7


# ======================================================================
# Shared utilities
# ======================================================================
@dataclass
class Prediction:
    model: Literal["historical", "tournament"]
    expected_home: float
    expected_away: float
    p_home_win: float
    p_draw: float
    p_away_win: float
    most_likely: tuple[int, int, float]
    score_matrix: np.ndarray
    notes: str = ""


def _poisson_matrix(lambda_home: float, lambda_away: float) -> np.ndarray:
    """Independent bivariate Poisson — outer product of two Poisson PMFs.

    Simple version. For better calibration on low scores, plug in the
    Dixon-Coles τ(x,y,λ,μ,ρ) correction here.
    """
    from scipy.stats import poisson
    h = poisson.pmf(np.arange(MAX_GOALS + 1), lambda_home)
    a = poisson.pmf(np.arange(MAX_GOALS + 1), lambda_away)
    m = np.outer(h, a)
    return m / m.sum()


def _matrix_to_prediction(
    model: str, m: np.ndarray, lam_h: float, lam_a: float, notes: str = ""
) -> Prediction:
    n = m.shape[0]
    home_win = float(np.tril(m, -1).sum())   # rows > cols
    away_win = float(np.triu(m, 1).sum())    # cols > rows
    draw = float(np.diag(m).sum())
    idx = np.unravel_index(np.argmax(m), m.shape)
    return Prediction(
        model=model,  # type: ignore
        expected_home=lam_h,
        expected_away=lam_a,
        p_home_win=home_win,
        p_draw=draw,
        p_away_win=away_win,
        most_likely=(int(idx[0]), int(idx[1]), float(m[idx])),
        score_matrix=m,
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


class HistoricalModel:
    """Two independent Poisson GLMs: one for home goals, one for away goals."""

    def __init__(self):
        self.model_home: sm.GLM | None = None
        self.model_away: sm.GLM | None = None

    def fit(self, df: pd.DataFrame) -> None:
        X_h = sm.add_constant(df[HOME_FEATURES])
        X_a = sm.add_constant(df[AWAY_FEATURES])
        self.model_home = sm.GLM(df["home_goals"], X_h, family=sm.families.Poisson()).fit()
        self.model_away = sm.GLM(df["away_goals"], X_a, family=sm.families.Poisson()).fit()

    def predict_lambdas(self, f: MatchFeatures) -> tuple[float, float]:
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
        lam_h, lam_a = self.predict_lambdas(f)
        m = _poisson_matrix(lam_h, lam_a)
        return _matrix_to_prediction("historical", m, lam_h, lam_a)

    def save(self, path: Path = MODEL_PATH / "historical.pkl") -> None:
        with open(path, "wb") as f:
            pickle.dump({"home": self.model_home, "away": self.model_away}, f)

    @classmethod
    def load(cls, path: Path = MODEL_PATH / "historical.pkl") -> "HistoricalModel":
        with open(path, "rb") as f:
            obj = pickle.load(f)
        m = cls()
        m.model_home = obj["home"]
        m.model_away = obj["away"]
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

        m = _poisson_matrix(lam_h, lam_a)
        notes = (
            f"baseado em {home.matches_played} jogos do {home.team_code} "
            f"e {away.matches_played} do {away.team_code} na Copa 2026"
        )
        return _matrix_to_prediction("tournament", m, lam_h, lam_a, notes)


# ======================================================================
# CLI: train / inspect
# ======================================================================
@click.group()
def cli():
    """Model training and inspection."""


@cli.command("train-historical")
@click.option("--since", default="2020-01-01")
def train_historical(since: str):
    """Train Modelo A on historical international matches."""
    click.echo("Building training set...")
    df = build_training_set(since=since)
    click.echo(f"  {len(df)} matches")
    click.echo("Fitting Poisson GLMs...")
    m = HistoricalModel()
    m.fit(df)
    m.save()
    click.echo("✓ Saved to models_artifacts/historical.pkl")
    click.echo("\nHome goals model summary:")
    click.echo(m.model_home.summary().tables[1])


@cli.command("inspect-tournament")
def inspect_tournament():
    """Print current tournament state per team."""
    state = build_tournament_state()
    for s in sorted(state.values(), key=lambda x: -x.matches_played):
        if s.matches_played == 0:
            continue
        click.echo(
            f"{s.team_code:>3} | played={s.matches_played} "
            f"GF={s.goals_scored_total} GA={s.goals_conceded_total} "
            f"prior_elo={s.prior_elo:.0f}"
        )


if __name__ == "__main__":
    cli()

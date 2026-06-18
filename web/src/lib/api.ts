// Thin typed client for the Copa Predictor FastAPI backend.

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";

export type Team = {
  id: number;
  name: string;
  code: string | null;
  country?: string | null;
  flag_url: string | null;
};

export type Fixture = {
  id: number;
  round: string | null;
  group: string | null;
  matchday: number | null;
  date_utc: string;
  venue_city: string | null;
  status: string;
  home: Team;
  away: Team;
  home_goals: number | null;
  away_goals: number | null;
};

export type FeatureRow = {
  label: string;
  home: number | string | null;
  away: number | string | null;
};

export type Prediction = {
  model: "tournament" | "historical";
  expected_home: number;
  expected_away: number;
  p_home_win: number;
  p_draw: number;
  p_away_win: number;
  most_likely: [number, number, number];
  score_matrix: number[][];
  notes: string;
  features: FeatureRow[] | null;
  home: Team;
  away: Team;
};

export type PredictResponse = {
  home: Team;
  away: Team;
  date_utc: string;
  predictions: Prediction[];
};

export type StandingRow = {
  team: Team;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  gf: number;
  ga: number;
  gd: number;
  points: number;
};

export type Standings = Record<string, StandingRow[]>;

export type TeamDetail = {
  team: Team;
  elo: number | null;
  form_gf: number;
  form_ga: number;
  tournament: {
    matches_played: number;
    goals_scored: number;
    goals_conceded: number;
  };
  matches: Fixture[];
};

export type RefreshResult = {
  interval_seconds: number;
  status: string;
  at: string | null;
  result: { teams: number; fixtures: number; finished: number; skipped: number } | null;
  error: string | null;
};

export type MonitorSnapshot = {
  date: string;
  n_games: number;
  draw_rate_real: number;
  A_acc: number;
  A_rps: number;
  A_brier: number;
  A_logloss: number;
  A_draw_pred: number;
  B_acc: number;
  B_rps: number;
  B_brier: number;
  B_logloss: number;
  B_draw_pred: number;
  base_rps: number;
  base_brier: number;
};

export type Recalibration = {
  state: "green" | "yellow" | "red";
  recommend: boolean;
  eligible: boolean;
  n_games: number;
  min_games: number;
  draw_real: number;
  draw_pred: number;
  z: number;
  days_persistent: number;
  persist_days: number;
  reason: string;
};

export type MonitorData = {
  history: MonitorSnapshot[];
  latest: MonitorSnapshot | null;
  recalibration: Recalibration;
};

async function get<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  teams: () => get<Team[]>("/api/teams"),
  fixtures: (params?: { status?: string; group?: string; matchday?: number }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.group) q.set("group", params.group);
    if (params?.matchday != null) q.set("matchday", String(params.matchday));
    const qs = q.toString();
    return get<Fixture[]>(`/api/fixtures${qs ? `?${qs}` : ""}`);
  },
  standings: () => get<Standings>("/api/standings"),
  team: (id: number) => get<TeamDetail>(`/api/teams/${id}`),
  predict: (params: {
    home?: string;
    away?: string;
    fixtureId?: number;
    historical?: boolean;
  }) => {
    const q = new URLSearchParams();
    if (params.home) q.set("home", params.home);
    if (params.away) q.set("away", params.away);
    if (params.fixtureId != null) q.set("fixture_id", String(params.fixtureId));
    if (params.historical) q.set("historical", "true");
    return get<PredictResponse>(`/api/predict?${q.toString()}`);
  },
  refresh: () => get<RefreshResult>("/api/refresh", { method: "POST" }),
  monitor: {
    history: () => get<MonitorData>("/api/monitor/history"),
    run: () => get<MonitorData>("/api/monitor/run", { method: "POST" }),
  },
};

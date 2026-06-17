-- Copa Predictor schema
-- Designed for SQLite. Adjust types if migrating to Postgres.

PRAGMA foreign_keys = ON;

-- =========================================================
-- TEAMS
-- =========================================================
CREATE TABLE IF NOT EXISTS teams (
    id              INTEGER PRIMARY KEY,         -- API-Football team id
    name            TEXT NOT NULL,
    code            TEXT,                        -- FIFA 3-letter code (BRA, ARG, ...)
    country         TEXT,
    flag_url        TEXT,
    is_wc2026       INTEGER DEFAULT 0            -- qualified for World Cup 2026
);

CREATE INDEX IF NOT EXISTS idx_teams_code ON teams(code);
CREATE INDEX IF NOT EXISTS idx_teams_wc2026 ON teams(is_wc2026);

-- =========================================================
-- FIXTURES (all matches: WC2026 + historical international matches)
-- =========================================================
CREATE TABLE IF NOT EXISTS fixtures (
    id              INTEGER PRIMARY KEY,         -- API-Football fixture id
    league_id       INTEGER NOT NULL,
    season          INTEGER NOT NULL,
    round           TEXT,                        -- 'Group A - 1', 'Round of 16', ...
    date_utc        TEXT NOT NULL,               -- ISO 8601
    venue_city      TEXT,
    venue_country   TEXT,
    is_neutral      INTEGER DEFAULT 1,
    status          TEXT,                        -- NS, 1H, HT, 2H, FT, ...
    home_team_id    INTEGER NOT NULL REFERENCES teams(id),
    away_team_id    INTEGER NOT NULL REFERENCES teams(id),
    home_goals      INTEGER,                     -- NULL while NS
    away_goals      INTEGER,
    home_goals_ht   INTEGER,
    away_goals_ht   INTEGER,
    is_wc2026       INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_fixtures_date ON fixtures(date_utc);
CREATE INDEX IF NOT EXISTS idx_fixtures_teams ON fixtures(home_team_id, away_team_id);
CREATE INDEX IF NOT EXISTS idx_fixtures_wc2026 ON fixtures(is_wc2026);
CREATE INDEX IF NOT EXISTS idx_fixtures_status ON fixtures(status);

-- =========================================================
-- MATCH STATISTICS (per team per fixture)
-- =========================================================
CREATE TABLE IF NOT EXISTS match_stats (
    fixture_id          INTEGER NOT NULL REFERENCES fixtures(id),
    team_id             INTEGER NOT NULL REFERENCES teams(id),
    shots_total         INTEGER,
    shots_on_target     INTEGER,
    shots_inside_box    INTEGER,
    possession_pct      REAL,
    passes_total        INTEGER,
    passes_accuracy_pct REAL,
    fouls               INTEGER,
    corners             INTEGER,
    offsides            INTEGER,
    yellow_cards        INTEGER,
    red_cards           INTEGER,
    xg                  REAL,                    -- if available
    PRIMARY KEY (fixture_id, team_id)
);

-- =========================================================
-- ELO RATINGS (snapshot per team at a given date)
-- =========================================================
CREATE TABLE IF NOT EXISTS elo_ratings (
    team_code       TEXT NOT NULL,
    snapshot_date   TEXT NOT NULL,               -- YYYY-MM-DD
    elo             REAL NOT NULL,
    rank            INTEGER,
    PRIMARY KEY (team_code, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_elo_date ON elo_ratings(snapshot_date);

-- =========================================================
-- PREDICTIONS (stored model outputs for comparison / backtesting)
-- =========================================================
CREATE TABLE IF NOT EXISTS predictions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id      INTEGER NOT NULL REFERENCES fixtures(id),
    model           TEXT NOT NULL,               -- 'historical' | 'tournament'
    created_at      TEXT NOT NULL,
    expected_home   REAL NOT NULL,
    expected_away   REAL NOT NULL,
    p_home_win      REAL NOT NULL,
    p_draw          REAL NOT NULL,
    p_away_win      REAL NOT NULL,
    most_likely_h   INTEGER NOT NULL,
    most_likely_a   INTEGER NOT NULL,
    most_likely_p   REAL NOT NULL,
    meta_json       TEXT                          -- full distribution, features used, etc.
);

CREATE INDEX IF NOT EXISTS idx_predictions_fixture ON predictions(fixture_id);
CREATE INDEX IF NOT EXISTS idx_predictions_model ON predictions(model);

-- =========================================================
-- API CACHE (transparent caching for API-Football responses)
-- =========================================================
CREATE TABLE IF NOT EXISTS api_cache (
    cache_key       TEXT PRIMARY KEY,
    response_json   TEXT NOT NULL,
    fetched_at      TEXT NOT NULL,
    expires_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cache_expires ON api_cache(expires_at);

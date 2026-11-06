CREATE TABLE IF NOT EXISTS games (
 game_id TEXT PRIMARY KEY,
 season INTEGER NOT NULL CHECK (season BETWEEN 1999 AND 2100),
 gameday DATE NOT NULL,
 home_team TEXT NOT NULL,
 away_team TEXT NOT NULL CHECK (away_team <> home_team),
 payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS games_season_day ON games(season, gameday);
CREATE TABLE IF NOT EXISTS outcomes (
 stream_id TEXT PRIMARY KEY, game_id TEXT,
 decision TEXT NOT NULL CHECK (decision IN ('accepted','rejected','duplicate')),
 reason TEXT NOT NULL, payload TEXT,
 recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

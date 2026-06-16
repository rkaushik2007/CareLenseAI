-- CareLenseAI planner state (Lakebase Postgres)

CREATE TABLE IF NOT EXISTS planner_watch (
  planner_id TEXT NOT NULL,
  unit_key   TEXT NOT NULL,
  capability TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (planner_id, unit_key, capability)
);

CREATE TABLE IF NOT EXISTS planner_notes (
  planner_id TEXT NOT NULL,
  unit_key   TEXT NOT NULL,
  capability TEXT NOT NULL,
  note       TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (planner_id, unit_key, capability)
);

CREATE TABLE IF NOT EXISTS planner_overrides (
  planner_id TEXT NOT NULL,
  unit_key   TEXT NOT NULL,
  capability TEXT NOT NULL,
  verdict    TEXT CHECK (verdict IN ('desert','blind','served','unknown')),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (planner_id, unit_key, capability)
);

CREATE TABLE IF NOT EXISTS planner_scenarios (
  planner_id TEXT NOT NULL,
  name       TEXT NOT NULL,
  cap        TEXT NOT NULL,
  grain      TEXT NOT NULL,
  overlay    BOOLEAN DEFAULT FALSE,
  sort       TEXT DEFAULT 'priority',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (planner_id, name)
);

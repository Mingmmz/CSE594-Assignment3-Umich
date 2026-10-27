-- PostgreSQL: init-db installs these tables in the private a3_study schema.
-- SQLite uses the same table definitions for explicit local practice/testing.
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL UNIQUE,
    participant_code TEXT NOT NULL,
    display_code TEXT NOT NULL,
    condition TEXT NOT NULL CHECK (condition IN ('baseline', 'ai')),
    attempt_no INTEGER NOT NULL,
    sequence_no INTEGER NOT NULL,
    first_condition TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('attention', 'active', 'survey', 'completed')),
    task_count INTEGER NOT NULL,
    dataset_version TEXT NOT NULL,
    familiarity INTEGER,
    consent_at TEXT NOT NULL,
    attention_failures INTEGER NOT NULL DEFAULT 0,
    attention_passed_at TEXT,
    workload INTEGER,
    usefulness INTEGER,
    feedback TEXT,
    survey_submitted_at TEXT,
    completed_at TEXT,
    completion_code TEXT NOT NULL UNIQUE,
    UNIQUE (participant_code, condition, attempt_no),
    UNIQUE (participant_code, sequence_no)
);
CREATE TABLE IF NOT EXISTS trials (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    position INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    prior_exposures INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'review', 'submitted', 'skipped')),
    viewed_at TEXT,
    image_ready_at TEXT,
    initial_label TEXT CHECK (initial_label IN ('genuine', 'fake')),
    initial_confidence INTEGER CHECK (initial_confidence BETWEEN 1 AND 5),
    initial_submitted_at TEXT,
    ai_revealed_at TEXT,
    shown_prediction TEXT,
    shown_confidence REAL,
    shown_gradcam TEXT,
    ai_assets_ready_at TEXT,
    final_label TEXT CHECK (final_label IN ('genuine', 'fake')),
    final_confidence INTEGER CHECK (final_confidence BETWEEN 1 AND 5),
    uncertain INTEGER,
    trust INTEGER CHECK (trust BETWEEN 1 AND 5),
    reasons TEXT,
    comment TEXT,
    submitted_at TEXT,
    skip_reason TEXT,
    UNIQUE (session_id, position),
    UNIQUE (session_id, item_id)
);
CREATE TABLE IF NOT EXISTS attention_events (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    answer TEXT NOT NULL,
    passed INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_participant_idx ON sessions(participant_code);
CREATE INDEX IF NOT EXISTS trials_session_idx ON trials(session_id, position);

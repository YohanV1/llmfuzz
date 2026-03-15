CREATE TABLE IF NOT EXISTS fuzz_sessions (
    session_id TEXT PRIMARY KEY,
    target_id TEXT NOT NULL,
    target_json TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    final_line_coverage REAL,
    final_branch_coverage REAL,
    total_inputs INTEGER DEFAULT 0,
    total_iterations INTEGER DEFAULT 0,
    plateau_detected INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS execution_results (
    input_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES fuzz_sessions(session_id),
    target_id TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    args_json TEXT NOT NULL,
    kwargs_json TEXT NOT NULL,
    outcome TEXT NOT NULL,
    exception_type TEXT,
    exception_message TEXT,
    traceback TEXT,
    duration_ms REAL,
    new_lines_covered TEXT,
    new_branches_covered TEXT,
    executed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS crash_reports (
    crash_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES fuzz_sessions(session_id),
    target_id TEXT NOT NULL,
    input_id TEXT NOT NULL,
    exception_type TEXT NOT NULL,
    exception_message TEXT NOT NULL,
    traceback TEXT NOT NULL,
    reproducer_code TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    first_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS coverage_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES fuzz_sessions(session_id),
    target_id TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    lines_total INTEGER,
    lines_covered INTEGER,
    branches_total INTEGER,
    branches_covered INTEGER,
    line_coverage_pct REAL,
    branch_coverage_pct REAL,
    UNIQUE(session_id, iteration)
);

CREATE INDEX IF NOT EXISTS idx_results_session ON execution_results(session_id);
CREATE INDEX IF NOT EXISTS idx_crashes_session ON crash_reports(session_id);
CREATE INDEX IF NOT EXISTS idx_coverage_session ON coverage_snapshots(session_id);

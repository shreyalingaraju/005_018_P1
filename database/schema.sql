-- Campus NetWatch - SQLite schema
-- Foreign keys are enabled per-connection (PRAGMA foreign_keys = ON).

CREATE TABLE IF NOT EXISTS users (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT    NOT NULL,
    institutional_id TEXT    NOT NULL UNIQUE,
    email            TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash    TEXT    NOT NULL,
    role             TEXT    NOT NULL DEFAULT 'user'
                     CHECK (role IN ('user', 'administrator', 'central_admin')),
    created_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS administrators (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    admin_code    TEXT    NOT NULL UNIQUE,          -- e.g. Admin_HOST, Backup_LAB, Central_Admin
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    assigned_zone TEXT    NOT NULL,                 -- location code or CENTRAL
    admin_role    TEXT    NOT NULL CHECK (admin_role IN ('primary', 'backup', 'central')),
    availability  TEXT    NOT NULL DEFAULT 'Available' CHECK (availability IN ('Available', 'Busy')),
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS campus_zones (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    location_code    TEXT    NOT NULL UNIQUE,
    location_name    TEXT    NOT NULL,
    primary_admin_id INTEGER REFERENCES administrators(id) ON DELETE SET NULL,
    backup_admin_id  INTEGER REFERENCES administrators(id) ON DELETE SET NULL,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Routing table: source of truth for zone -> administrator mapping.
CREATE TABLE IF NOT EXISTS routing_table (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id          INTEGER NOT NULL UNIQUE REFERENCES campus_zones(id) ON DELETE CASCADE,
    primary_admin_id INTEGER REFERENCES administrators(id) ON DELETE SET NULL,
    backup_admin_id  INTEGER REFERENCES administrators(id) ON DELETE SET NULL,
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS complaints (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id        TEXT    NOT NULL UNIQUE,     -- CNFR-YYYYMMDD-XXXXXX
    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_name           TEXT    NOT NULL,
    institutional_id    TEXT    NOT NULL,
    device_type         TEXT    NOT NULL CHECK (device_type IN ('WIFI', 'LAN')),
    location_code       TEXT    NOT NULL,
    floor_number        INTEGER NOT NULL CHECK (floor_number BETWEEN 0 AND 9),
    identifier          TEXT    NOT NULL,
    description         TEXT    NOT NULL,
    category            TEXT    NOT NULL
                        CHECK (category IN ('Connectivity', 'Hardware', 'Configuration', 'Security', 'Unknown')),
    matched_keywords    TEXT    NOT NULL DEFAULT '{}',   -- JSON {category: [keywords]}
    detected_categories TEXT    NOT NULL DEFAULT '[]',   -- JSON list
    priority            TEXT    NOT NULL CHECK (priority IN ('Critical', 'High', 'Medium', 'Low')),
    priority_rank       INTEGER NOT NULL,
    status              TEXT    NOT NULL DEFAULT 'Pending'
                        CHECK (status IN ('Pending', 'Assigned', 'In Progress', 'Resolved')),
    assigned_admin_id   INTEGER REFERENCES administrators(id) ON DELETE SET NULL,
    routed_zone         TEXT,                        -- zone used for routing (or CENTRAL)
    submission_time     TEXT    NOT NULL,
    assigned_time       TEXT,
    in_progress_time    TEXT,
    resolved_time       TEXT,
    updated_at          TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS complaint_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id    INTEGER NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    action          TEXT    NOT NULL,   -- CREATED, ASSIGNED, QUEUED, REASSIGNED, STATUS_CHANGE, FORWARDED_CENTRAL
    previous_status TEXT,
    new_status      TEXT    NOT NULL,
    changed_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,   -- NULL = routing system
    changed_by_name TEXT    NOT NULL DEFAULT 'Routing Engine',
    remarks         TEXT,
    changed_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS waiting_queue (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id   INTEGER NOT NULL UNIQUE REFERENCES complaints(id) ON DELETE CASCADE,
    zone_code      TEXT    NOT NULL,
    priority       TEXT    NOT NULL,
    priority_rank  INTEGER NOT NULL,
    queue_position INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    actor_name    TEXT    NOT NULL DEFAULT 'System',
    action        TEXT    NOT NULL,
    entity_type   TEXT    NOT NULL,
    entity_id     TEXT,
    details       TEXT,
    created_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_complaints_user      ON complaints(user_id);
CREATE INDEX IF NOT EXISTS idx_complaints_admin     ON complaints(assigned_admin_id);
CREATE INDEX IF NOT EXISTS idx_complaints_status    ON complaints(status);
CREATE INDEX IF NOT EXISTS idx_complaints_location  ON complaints(location_code);
CREATE INDEX IF NOT EXISTS idx_complaints_submitted ON complaints(submission_time);
CREATE INDEX IF NOT EXISTS idx_history_complaint    ON complaint_history(complaint_id);
CREATE INDEX IF NOT EXISTS idx_queue_order          ON waiting_queue(zone_code, priority_rank, created_at, id);
CREATE INDEX IF NOT EXISTS idx_audit_created        ON audit_logs(created_at);

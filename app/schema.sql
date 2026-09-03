CREATE TABLE IF NOT EXISTS posts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id    INTEGER REFERENCES posts(id),
    category     TEXT    NOT NULL,
    body         TEXT    NOT NULL,
    author_name  TEXT,
    location     TEXT,
    author_token TEXT    NOT NULL,
    is_admin     INTEGER NOT NULL DEFAULT 0,
    is_resolved  INTEGER NOT NULL DEFAULT 0,
    resolved_at  TEXT,
    is_pinned    INTEGER NOT NULL DEFAULT 0,
    is_deleted   INTEGER NOT NULL DEFAULT 0,
    post_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS shelters (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    name                     TEXT NOT NULL,
    address                  TEXT,
    prefecture               TEXT,
    city                     TEXT,
    capacity                 INTEGER,
    disaster_flood           INTEGER DEFAULT 0,
    disaster_landslide_etc   INTEGER DEFAULT 0,
    disaster_stormsurge      INTEGER DEFAULT 0,
    disaster_earthquake      INTEGER DEFAULT 0,
    disaster_tsunami         INTEGER DEFAULT 0,
    disaster_large_scale_fire INTEGER DEFAULT 0,
    disaster_inland_flooding INTEGER DEFAULT 0,
    disaster_volcanicactivity INTEGER DEFAULT 0,
    is_active                INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_posts_timeline ON posts(is_deleted, parent_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_posts_parent   ON posts(parent_id);
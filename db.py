"""SQLite uloziste portalu zivotnich situaci.

Zadne zavislosti mimo standardni knihovnu. Databaze je jeden soubor
data/portal.sqlite3, ktery se da smazat a znovu vygenerovat.
"""

import json
import os
import sqlite3
import unicodedata

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
MANUAL_DIR = os.path.join(DATA_DIR, "manual")
LOG_DIR = os.path.join(BASE_DIR, "logs")
DB_PATH = os.path.join(DATA_DIR, "portal.sqlite3")

DEADLINE_STATUSES = ("verified", "manual_todo", "not_applicable")
SOURCE_TYPES = ("katalog_sluzeb", "praha13", "sbirka_zakonu", "manual")
AUDIENCES = ("all", "citizen", "foreigner")

SCHEMA = """
PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------------
-- Rucne overena data (deliverable 2). Plni je seed.py z data/manual/.
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS situations (
    id               INTEGER PRIMARY KEY,
    slug             TEXT NOT NULL UNIQUE,
    title_cs         TEXT NOT NULL,
    title_uk         TEXT,
    title_ru         TEXT,
    summary_cs       TEXT,
    summary_uk       TEXT,
    summary_ru       TEXT,
    category         TEXT NOT NULL,
    audience         TEXT NOT NULL CHECK (audience IN ('all','citizen','foreigner')),
    praha13_url      TEXT,
    katalog_keywords TEXT,
    sort_order       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS steps (
    id              INTEGER PRIMARY KEY,
    situation_id    INTEGER NOT NULL REFERENCES situations(id) ON DELETE CASCADE,
    step_order      INTEGER NOT NULL,
    title_cs        TEXT NOT NULL,
    title_uk        TEXT,
    title_ru        TEXT,
    body_cs         TEXT,
    body_uk         TEXT,
    body_ru         TEXT,
    deadline_text   TEXT,
    deadline_days   INTEGER,
    deadline_source TEXT,
    deadline_status TEXT NOT NULL CHECK (deadline_status IN ('verified','manual_todo','not_applicable')),
    sanction_text   TEXT,
    sanction_source TEXT,
    authority       TEXT,
    location        TEXT,
    office_hours    TEXT,
    documents       TEXT NOT NULL DEFAULT '[]',   -- JSON pole retezcu
    source_type     TEXT NOT NULL CHECK (source_type IN ('katalog_sluzeb','praha13','sbirka_zakonu','manual')),
    source_url      TEXT,
    verify_hint     TEXT,                          -- kde lhutu dohledat, kdyz je manual_todo
    UNIQUE (situation_id, step_order)
);

CREATE INDEX IF NOT EXISTS idx_steps_situation ON steps(situation_id, step_order);

-- ------------------------------------------------------------------
-- Stazena data (deliverable 1). Plni je parsers/.
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS katalog_services (
    id               TEXT PRIMARY KEY,   -- iri nebo kod sluzby
    code             TEXT,
    name             TEXT,
    description      TEXT,
    agenda_code      TEXT,
    agenda_name      TEXT,
    legal_norms      TEXT,               -- JSON pole
    channels         TEXT,               -- JSON pole
    ohlasovatel_id   TEXT,
    ohlasovatel_name TEXT,
    source_url       TEXT,
    raw              TEXT,               -- puvodni zaznam pro pozdejsi dotezeni
    fetched_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_katalog_name ON katalog_services(name);

CREATE TABLE IF NOT EXISTS praha13_pages (
    url                   TEXT PRIMARY KEY,
    title                 TEXT,
    department            TEXT,   -- bod 8 / 25
    address               TEXT,   -- bod 9
    office_hours          TEXT,   -- bod 9
    documents             TEXT,   -- bod 10 (JSON pole radku)
    forms                 TEXT,   -- bod 11 (JSON pole radku)
    fees                  TEXT,   -- bod 12
    deadline_text_raw     TEXT,   -- bod 13, POUZE k rucnimu overeni, nikam se neplni automaticky
    sanctions             TEXT,   -- bod 20
    responsible_department TEXT,  -- bod 25
    points                TEXT,   -- JSON {"cislo bodu": "text"}
    status                TEXT,   -- ok | partial | failed
    fetched_at            TEXT,
    parsed_at             TEXT
);

CREATE TABLE IF NOT EXISTS parse_log (
    id      INTEGER PRIMARY KEY,
    run_id  TEXT NOT NULL,
    ts      TEXT NOT NULL,
    source  TEXT NOT NULL,      -- katalog | praha13 | link
    target  TEXT,               -- url nebo id zaznamu
    status  TEXT NOT NULL,      -- ok | skipped | warning | error
    message TEXT
);

CREATE INDEX IF NOT EXISTS idx_parse_log_run ON parse_log(run_id, status);
"""


def normalize_text(value):
    """male pismeno + bez diakritiky: 'Škola' i 'skola' pak najdou totez.

    SQLite lower() pracuje jen s ASCII, proto se registruje jako vlastni funkce.
    """
    if value is None:
        return ""
    value = unicodedata.normalize("NFKD", str(value)).lower()
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def connect(path=DB_PATH):
    """Otevre spojeni. Adresare i schema vznikaji samy."""
    for directory in (DATA_DIR, CACHE_DIR, MANUAL_DIR, LOG_DIR):
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.create_function("norm", 1, normalize_text)
    return conn


def init(conn):
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def row_to_dict(row):
    return {key: row[key] for key in row.keys()}


def load_json_column(value, fallback=None):
    """documents/legal_norms drzime jako JSON text; rozbite hodnoty nemaji shodit API."""
    if not value:
        return fallback if fallback is not None else []
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return fallback if fallback is not None else []


def counts(conn):
    def one(sql):
        try:
            return conn.execute(sql).fetchone()[0]
        except sqlite3.Error:
            return 0

    return {
        "situations": one("SELECT COUNT(*) FROM situations"),
        "steps": one("SELECT COUNT(*) FROM steps"),
        "steps_verified": one("SELECT COUNT(*) FROM steps WHERE deadline_status='verified'"),
        "steps_manual_todo": one("SELECT COUNT(*) FROM steps WHERE deadline_status='manual_todo'"),
        "steps_not_applicable": one("SELECT COUNT(*) FROM steps WHERE deadline_status='not_applicable'"),
        "katalog_services": one("SELECT COUNT(*) FROM katalog_services"),
        "praha13_pages": one("SELECT COUNT(*) FROM praha13_pages"),
    }


if __name__ == "__main__":
    with connect() as c:
        init(c)
        print("OK: schema pripraveno v", DB_PATH)
        print(counts(c))

"""
database.py — SQLite persistence for leads, sessions, and tags.

Schema
──────
sessions  : one row per search run
leads     : one row per unique lead; FK → sessions
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from utils import get_logger, fingerprint

logger = get_logger("database")

_DB_PATH = Path("leads.db")


# ─── Schema ───────────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sector      TEXT NOT NULL,
    city        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    result_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS leads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint     TEXT UNIQUE NOT NULL,
    session_id      INTEGER REFERENCES sessions(id),
    name            TEXT,
    sector          TEXT,
    city            TEXT,
    instagram_url   TEXT,
    website_url     TEXT,
    phone           TEXT,
    email           TEXT,
    description     TEXT,
    source_url      TEXT,
    source_query    TEXT,
    followers_approx INTEGER,
    has_instagram   INTEGER,
    has_phone       INTEGER,
    has_email       INTEGER,
    is_shallow_site INTEGER,
    dp_score        INTEGER DEFAULT 0,
    quality_score   INTEGER DEFAULT 0,
    tag             TEXT DEFAULT 'Untagged',
    notes           TEXT DEFAULT '',
    created_at      TEXT NOT NULL
);
"""


# ─── Connection Helper ────────────────────────────────────────────────────────

def _get_conn(db_path: Path = _DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(db_path: Path = _DB_PATH) -> sqlite3.Connection:
    """Initialise the database and return an open connection."""
    conn = _get_conn(db_path)
    conn.executescript(_DDL)
    conn.commit()
    logger.info("Database ready at %s", db_path.resolve())
    return conn


# ─── Sessions ─────────────────────────────────────────────────────────────────

def create_session(conn: sqlite3.Connection, sector: str, city: str) -> int:
    cur = conn.execute(
        "INSERT INTO sessions (sector, city, created_at) VALUES (?, ?, ?)",
        (sector, city, datetime.now().isoformat()),
    )
    conn.commit()
    return cur.lastrowid


def update_session_count(conn: sqlite3.Connection, session_id: int, count: int) -> None:
    conn.execute(
        "UPDATE sessions SET result_count = ? WHERE id = ?",
        (count, session_id),
    )
    conn.commit()


def list_sessions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM sessions ORDER BY created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


# ─── Leads ────────────────────────────────────────────────────────────────────

_LEAD_COLUMNS = [
    "fingerprint", "session_id", "name", "sector", "city",
    "instagram_url", "website_url", "phone", "email", "description",
    "source_url", "source_query", "followers_approx",
    "has_instagram", "has_phone", "has_email", "is_shallow_site",
    "dp_score", "quality_score", "tag", "notes", "created_at",
]


def upsert_lead(
    conn: sqlite3.Connection,
    lead: dict,
    session_id: int,
) -> bool:
    """Insert lead if not already stored (by fingerprint). Returns True if new."""
    fp = fingerprint(
        lead.get("name", ""),
        lead.get("city", ""),
        lead.get("instagram_url", ""),
    )
    now = datetime.now().isoformat()

    row = {
        "fingerprint":     fp,
        "session_id":      session_id,
        "name":            lead.get("name", ""),
        "sector":          lead.get("sector", ""),
        "city":            lead.get("city", ""),
        "instagram_url":   lead.get("instagram_url", ""),
        "website_url":     lead.get("website_url", ""),
        "phone":           lead.get("phone", ""),
        "email":           lead.get("email", ""),
        "description":     lead.get("description", ""),
        "source_url":      lead.get("source_url", ""),
        "source_query":    lead.get("source_query", ""),
        "followers_approx": lead.get("followers_approx"),
        "has_instagram":   int(bool(lead.get("has_instagram"))),
        "has_phone":       int(bool(lead.get("has_phone"))),
        "has_email":       int(bool(lead.get("has_email"))),
        "is_shallow_site": int(bool(lead.get("is_shallow_site"))),
        "dp_score":        lead.get("dp_score", 0),
        "quality_score":   lead.get("quality_score", 0),
        "tag":             lead.get("tag", "Untagged"),
        "notes":           lead.get("notes", ""),
        "created_at":      now,
    }

    cols   = ", ".join(row.keys())
    blanks = ", ".join("?" * len(row))
    values = list(row.values())

    try:
        conn.execute(
            f"INSERT OR IGNORE INTO leads ({cols}) VALUES ({blanks})",
            values,
        )
        conn.commit()
        return bool(conn.execute(
            "SELECT changes()"
        ).fetchone()[0])
    except sqlite3.Error as e:
        logger.error("DB upsert error: %s", e)
        return False


def save_leads(
    conn: sqlite3.Connection,
    leads: list[dict],
    session_id: int,
) -> int:
    """Save multiple leads and return count of newly inserted rows."""
    count = 0
    for lead in leads:
        if upsert_lead(conn, lead, session_id):
            count += 1
    update_session_count(conn, session_id, count)
    logger.info("Saved %d new leads (session %d).", count, session_id)
    return count


def get_leads(
    conn: sqlite3.Connection,
    session_id: Optional[int] = None,
    sector: Optional[str] = None,
    city: Optional[str] = None,
    tag: Optional[str] = None,
) -> list[dict]:
    """Fetch leads with optional filters."""
    query  = "SELECT * FROM leads WHERE 1=1"
    params: list = []

    if session_id is not None:
        query += " AND session_id = ?"
        params.append(session_id)
    if sector:
        query += " AND sector LIKE ?"
        params.append(f"%{sector}%")
    if city:
        query += " AND city LIKE ?"
        params.append(f"%{city}%")
    if tag:
        query += " AND tag = ?"
        params.append(tag)

    query += " ORDER BY quality_score DESC, dp_score DESC"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def update_tag(conn: sqlite3.Connection, lead_id: int, tag: str, notes: str = "") -> None:
    conn.execute(
        "UPDATE leads SET tag = ?, notes = ? WHERE id = ?",
        (tag, notes, lead_id),
    )
    conn.commit()


def delete_session(conn: sqlite3.Connection, session_id: int) -> None:
    conn.execute("DELETE FROM leads WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    logger.info("Deleted session %d and its leads.", session_id)

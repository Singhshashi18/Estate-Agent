"""SQLite DB layer for local development."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "agent.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    external_id TEXT NOT NULL UNIQUE,
    subreddit TEXT, title TEXT, body TEXT, url TEXT, author TEXT,
    found_at TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'discovered'
);
CREATE TABLE IF NOT EXISTS classifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    is_relevant INTEGER NOT NULL,
    intent TEXT, reason TEXT,
    classified_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    reply_text TEXT NOT NULL,
    short_link TEXT,
    posted_at TEXT, posted_url TEXT,
    status TEXT DEFAULT 'pending'
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def insert_post(row: dict) -> int | None:
    with get_conn() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO posts
                   (platform, external_id, subreddit, title, body, url, author)
                   VALUES (:platform, :external_id, :subreddit, :title, :body, :url, :author)""",
                row,
            )
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None


def update_post_status(post_id: int, status: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE posts SET status = ? WHERE id = ?", (status, post_id))


def insert_classification(post_id: int, is_relevant: bool, intent: str, reason: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO classifications (post_id, is_relevant, intent, reason) VALUES (?, ?, ?, ?)",
            (post_id, int(is_relevant), intent, reason),
        )


def insert_reply(post_id: int, reply_text: str, short_link: str, status: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO replies (post_id, reply_text, short_link, status) VALUES (?, ?, ?, ?)",
            (post_id, reply_text, short_link, status),
        )
        return cur.lastrowid


def fetch_summary() -> dict:
    with get_conn() as conn:
        return {
            "posts": conn.execute("SELECT COUNT(*) c FROM posts").fetchone()["c"],
            "relevant": conn.execute("SELECT COUNT(*) c FROM classifications WHERE is_relevant=1").fetchone()["c"],
            "replies_drafted": conn.execute("SELECT COUNT(*) c FROM replies").fetchone()["c"],
            "replies_posted": conn.execute("SELECT COUNT(*) c FROM replies WHERE status='posted'").fetchone()["c"],
        }

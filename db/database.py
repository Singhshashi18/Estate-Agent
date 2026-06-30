"""Postgres DB layer."""
from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv()

DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Add it to .env, e.g. "
        "postgresql://user:pass@localhost:5432/estate_agent"
    )

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id              SERIAL PRIMARY KEY,
    platform        TEXT        NOT NULL,
    external_id     TEXT        NOT NULL UNIQUE,
    subreddit       TEXT,
    title           TEXT,
    body            TEXT,
    url             TEXT,
    author          TEXT,
    found_at        TIMESTAMPTZ DEFAULT NOW(),
    status          TEXT        DEFAULT 'discovered'
);

CREATE TABLE IF NOT EXISTS classifications (
    id              SERIAL PRIMARY KEY,
    post_id         INTEGER     NOT NULL REFERENCES posts(id),
    is_relevant     BOOLEAN     NOT NULL,
    intent          TEXT,
    reason          TEXT,
    classified_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS replies (
    id              SERIAL PRIMARY KEY,
    post_id         INTEGER     NOT NULL REFERENCES posts(id),
    reply_text      TEXT        NOT NULL,
    short_link      TEXT,
    posted_at       TIMESTAMPTZ,
    posted_url      TEXT,
    status          TEXT        DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS clicks (
    id              SERIAL PRIMARY KEY,
    short_code      TEXT        NOT NULL,
    clicked_at      TIMESTAMPTZ DEFAULT NOW(),
    user_agent      TEXT,
    ip              TEXT
);
"""


@contextmanager
def get_conn():
    with psycopg.connect(DB_URL, row_factory=dict_row, autocommit=False) as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(SCHEMA)


def insert_post(row: dict) -> int | None:
    """Insert a discovered post; returns row id or None if duplicate."""
    with get_conn() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO posts
                   (platform, external_id, subreddit, title, body, url, author)
                   VALUES (%(platform)s, %(external_id)s, %(subreddit)s,
                           %(title)s, %(body)s, %(url)s, %(author)s)
                   RETURNING id""",
                row,
            )
            return cur.fetchone()["id"]
        except psycopg.errors.UniqueViolation:
            return None


def update_post_status(post_id: int, status: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE posts SET status = %s WHERE id = %s", (status, post_id))


def insert_classification(post_id: int, is_relevant: bool, intent: str, reason: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO classifications (post_id, is_relevant, intent, reason)
               VALUES (%s, %s, %s, %s)""",
            (post_id, bool(is_relevant), intent, reason),
        )


def insert_reply(post_id: int, reply_text: str, short_link: str, status: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO replies (post_id, reply_text, short_link, status)
               VALUES (%s, %s, %s, %s)
               RETURNING id""",
            (post_id, reply_text, short_link, status),
        )
        return cur.fetchone()["id"]


def fetch_summary() -> dict:
    with get_conn() as conn:
        return {
            "posts":           conn.execute("SELECT COUNT(*) AS c FROM posts").fetchone()["c"],
            "relevant":        conn.execute("SELECT COUNT(*) AS c FROM classifications WHERE is_relevant = TRUE").fetchone()["c"],
            "replies_drafted": conn.execute("SELECT COUNT(*) AS c FROM replies").fetchone()["c"],
            "replies_posted":  conn.execute("SELECT COUNT(*) AS c FROM replies WHERE status = 'posted'").fetchone()["c"],
        }

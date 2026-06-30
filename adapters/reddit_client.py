"""Shared PRAW Reddit client (singleton).

Returns None if credentials are missing — callers can then fall back to
public JSON / fixtures.
"""
from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _required_creds() -> dict[str, str]:
    return {
        "client_id":     os.getenv("REDDIT_CLIENT_ID", ""),
        "client_secret": os.getenv("REDDIT_CLIENT_SECRET", ""),
        "username":      os.getenv("REDDIT_USERNAME", ""),
        "password":      os.getenv("REDDIT_PASSWORD", ""),
        "user_agent":    os.getenv("REDDIT_USER_AGENT", "estate-agent/1.0"),
    }


def have_creds() -> bool:
    c = _required_creds()
    return all(c[k] for k in ("client_id", "client_secret", "username", "password"))


@lru_cache(maxsize=1)
def get_reddit():
    """Returns an authenticated PRAW instance, or None if creds missing."""
    if not have_creds():
        return None
    import praw
    c = _required_creds()
    reddit = praw.Reddit(
        client_id=c["client_id"],
        client_secret=c["client_secret"],
        username=c["username"],
        password=c["password"],
        user_agent=c["user_agent"],
        check_for_async=False,
    )
    # Sanity check — forces auth handshake; raises if creds bad.
    _ = reddit.user.me()
    return reddit

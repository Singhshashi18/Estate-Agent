"""Posting layer.

Order of checks:
  1. DRY_RUN=true        -> never posts, returns 'dry_run'
  2. HUMAN_APPROVAL=true -> queues as 'pending' for manual approval
  3. otherwise           -> posts for real via PRAW
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from adapters.reddit_client import get_reddit, have_creds

load_dotenv()

DRY_RUN        = os.getenv("DRY_RUN", "true").lower() == "true"
HUMAN_APPROVAL = os.getenv("HUMAN_APPROVAL", "true").lower() == "true"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def post_reply(post: dict, reply_text: str) -> dict:
    """Returns {status, posted_url, posted_at}."""
    if DRY_RUN:
        return {"status": "dry_run", "posted_url": None, "posted_at": _now_iso()}
    if HUMAN_APPROVAL:
        return {"status": "pending", "posted_url": None, "posted_at": None}
    if post.get("platform") == "reddit":
        return _post_reddit_real(post, reply_text)
    return {"status": "failed", "posted_url": None, "posted_at": None}


def _post_reddit_real(post: dict, reply_text: str) -> dict:
    if not have_creds():
        return {"status": "failed", "posted_url": None, "posted_at": None,
                "error": "Reddit creds missing"}
    try:
        reddit = get_reddit()
        submission = reddit.submission(id=post["external_id"])
        comment = submission.reply(reply_text)
        return {
            "status":     "posted",
            "posted_url": f"https://www.reddit.com{comment.permalink}",
            "posted_at":  _now_iso(),
        }
    except Exception as e:
        return {"status": "failed", "posted_url": None, "posted_at": _now_iso(),
                "error": str(e)[:200]}

"""Reddit discovery.

Tries PRAW (authenticated) first when creds exist, falls back to public JSON,
finally falls back to local fixtures so the pipeline never breaks.
"""
from __future__ import annotations

import time
from typing import Iterable

import requests

from adapters.fixtures import FIXTURE_POSTS
from adapters.reddit_client import get_reddit, have_creds

UA = {"User-Agent": "estate-agent-discovery/0.1"}


def fetch_subreddit_new_praw(subreddit: str, limit: int = 25) -> list[dict]:
    reddit = get_reddit()
    if reddit is None:
        raise RuntimeError("No Reddit creds")
    out: list[dict] = []
    for s in reddit.subreddit(subreddit).new(limit=limit):
        out.append({
            "platform":    "reddit",
            "external_id": s.id,
            "subreddit":   str(s.subreddit),
            "title":       s.title or "",
            "body":        s.selftext or "",
            "url":         f"https://www.reddit.com{s.permalink}",
            "author":      str(s.author) if s.author else None,
        })
    return out


def fetch_subreddit_new_public(subreddit: str, limit: int = 10) -> list[dict]:
    url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}"
    resp = requests.get(url, headers=UA, timeout=15)
    resp.raise_for_status()
    children = resp.json().get("data", {}).get("children", [])
    out = []
    for c in children:
        d = c.get("data", {})
        out.append({
            "platform":    "reddit",
            "external_id": d.get("id"),
            "subreddit":   d.get("subreddit"),
            "title":       d.get("title", ""),
            "body":        d.get("selftext", ""),
            "url":         f"https://www.reddit.com{d.get('permalink', '')}",
            "author":      d.get("author"),
        })
    return out


def keyword_match(post: dict, keywords: Iterable[str]) -> bool:
    text = f"{post.get('title', '')} {post.get('body', '')}".lower()
    return any(k.lower() in text for k in keywords)


def discover(subreddits: list[str], keywords: list[str], per_sub: int = 10) -> list[dict]:
    """Pull newest posts from each subreddit, keep ones matching keywords."""
    use_praw = have_creds()
    if use_praw:
        print("  [discover] using authenticated PRAW")
    else:
        print("  [discover] no Reddit creds -> trying public JSON")

    results: list[dict] = []
    failures = 0
    for sub in subreddits:
        try:
            if use_praw:
                posts = fetch_subreddit_new_praw(sub, limit=per_sub)
            else:
                posts = fetch_subreddit_new_public(sub, limit=per_sub)
        except Exception as e:
            print(f"  ! failed r/{sub}: {e}")
            failures += 1
            continue
        matched = [p for p in posts if keyword_match(p, keywords)]
        results.extend(matched)
        time.sleep(1)

    if not results and failures == len(subreddits):
        print("  > all requests failed; falling back to local fixtures")
        results = list(FIXTURE_POSTS)
    return results

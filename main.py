"""End-to-end pipeline.

Run:    python main.py
Flow:   validate config -> discover -> classify -> generate -> attach link
        -> post (mock or real) -> log -> summary
"""
from __future__ import annotations

import time
from collections import defaultdict

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import config
from adapters.reddit_public import discover
from db.database import (
    fetch_summary,
    init_db,
    insert_classification,
    insert_post,
    insert_reply,
    update_post_status,
)
from workers.links import build_tracked_link
from workers.llm import classify, generate_reply
from workers.poster import post_reply

console = Console()


def run_pipeline() -> None:
    config.validate_or_exit()
    init_db()

    mode = "MOCK_LLM" if config.MOCK_LLM else "REAL_LLM"
    if config.DRY_RUN:
        posting = "DRY_RUN"
    elif config.HUMAN_APPROVAL:
        posting = "HUMAN_APPROVAL"
    else:
        posting = "LIVE"

    console.print(Panel.fit(
        f"[bold]Estate-Planning Engagement Agent[/bold]\n"
        f"mode: [cyan]{mode}[/cyan]   posting: [yellow]{posting}[/yellow]\n"
        f"subs: {config.SUBREDDITS}\nkeywords: {config.KEYWORDS}\n"
        f"caps: max/run={config.MAX_REPLIES_PER_RUN} "
        f"max/sub={config.MAX_REPLIES_PER_SUB_RUN} "
        f"delay={config.REPLY_DELAY_SECONDS}s",
        title="Pipeline start",
    ))

    console.rule("[bold]1. Discover")
    posts = discover(config.SUBREDDITS, config.KEYWORDS, per_sub=config.POSTS_PER_SUBREDDIT)
    console.print(f"  found [green]{len(posts)}[/green] keyword-matching posts")

    new_post_ids: list[tuple[int, dict]] = []
    for p in posts:
        pid = insert_post(p)
        if pid:
            new_post_ids.append((pid, p))
    console.print(f"  inserted [green]{len(new_post_ids)}[/green] new posts (rest were duplicates)")

    console.rule("[bold]2-5. Classify  ->  Generate  ->  Link  ->  Post")
    table = Table(show_lines=True)
    table.add_column("#",      style="dim", width=3)
    table.add_column("Sub",    style="cyan", width=18)
    table.add_column("Title",  style="white", overflow="fold")
    table.add_column("Rel?",   width=5)
    table.add_column("Action", style="green")

    replies_total = 0
    replies_per_sub: dict[str, int] = defaultdict(int)

    for i, (pid, post) in enumerate(new_post_ids, start=1):
        verdict = classify(post)
        insert_classification(pid, verdict["is_relevant"], verdict["intent"], verdict["reason"])

        if not verdict["is_relevant"]:
            update_post_status(pid, "rejected")
            table.add_row(str(i), post["subreddit"], post["title"][:80],
                          "[red]no[/red]", f"skip ({verdict['intent']})")
            continue

        sub = post.get("subreddit", "")
        if replies_total >= config.MAX_REPLIES_PER_RUN:
            update_post_status(pid, "skipped")
            table.add_row(str(i), sub, post["title"][:80],
                          "[green]yes[/green]", "skip (run cap)")
            continue
        if replies_per_sub[sub] >= config.MAX_REPLIES_PER_SUB_RUN:
            update_post_status(pid, "skipped")
            table.add_row(str(i), sub, post["title"][:80],
                          "[green]yes[/green]", "skip (sub cap)")
            continue

        reply_template = generate_reply(post)
        short_link, _full = build_tracked_link(post)
        reply_text = reply_template.replace("{LINK}", short_link)

        result = post_reply(post, reply_text)
        insert_reply(pid, reply_text, short_link, result["status"])
        update_post_status(pid, "replied" if result["status"] == "posted" else "drafted")

        replies_total += 1
        replies_per_sub[sub] += 1

        table.add_row(str(i), sub, post["title"][:80],
                      "[green]yes[/green]", f"reply [{result['status']}]")

        if result["status"] == "posted" and config.REPLY_DELAY_SECONDS > 0:
            time.sleep(config.REPLY_DELAY_SECONDS)

    console.print(table)

    console.rule("[bold]6. Summary")
    s = fetch_summary()
    summary = Table.grid(padding=(0, 2))
    summary.add_row("Posts discovered:",  str(s["posts"]))
    summary.add_row("Relevant (passed classifier):", str(s["relevant"]))
    summary.add_row("Replies drafted:", str(s["replies_drafted"]))
    summary.add_row("Replies actually posted:", str(s["replies_posted"]))
    summary.add_row("Replies in THIS run:", str(replies_total))
    console.print(summary)
    console.print("\n[dim]DB:[/dim] Postgres at $DATABASE_URL   (use psql or any Postgres GUI)\n")


if __name__ == "__main__":
    run_pipeline()

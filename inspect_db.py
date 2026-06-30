"""Quick peek into agent.db — shows latest posts, classifications, and drafted replies."""
from rich.console import Console
from rich.table import Table

from db.database import get_conn

console = Console()


def show(query: str, title: str, cols: list[str]) -> None:
    with get_conn() as conn:
        rows = conn.execute(query).fetchall()
    t = Table(title=title, show_lines=True)
    for c in cols:
        t.add_column(c, overflow="fold")
    for r in rows:
        t.add_row(*[str(r[c]) if r[c] is not None else "" for c in cols])
    console.print(t)


if __name__ == "__main__":
    show(
        "SELECT id, subreddit, title, status FROM posts ORDER BY id DESC LIMIT 15",
        "Latest posts",
        ["id", "subreddit", "title", "status"],
    )
    show(
        """SELECT c.post_id, c.is_relevant, c.intent, c.reason
           FROM classifications c ORDER BY c.id DESC LIMIT 10""",
        "Latest classifications",
        ["post_id", "is_relevant", "intent", "reason"],
    )
    show(
        """SELECT id, post_id, status, short_link, substr(reply_text,1,140) AS preview
           FROM replies ORDER BY id DESC LIMIT 5""",
        "Latest drafted replies",
        ["id", "post_id", "status", "short_link", "preview"],
    )

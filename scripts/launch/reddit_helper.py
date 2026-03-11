"""Reddit post helper — schedule posts, monitor replies, suggest responses.

Requires: pip install praw

Setup:
    1. Go to https://www.reddit.com/prefs/apps
    2. Create app → "script" type
    3. Note: client_id (under app name), client_secret
    4. Set env vars:
        export REDDIT_CLIENT_ID="..."
        export REDDIT_CLIENT_SECRET="..."
        export REDDIT_USERNAME="..."
        export REDDIT_PASSWORD="..."

Usage:
    # Post to a subreddit
    uv run python scripts/launch/reddit_helper.py post --subreddit ClaudeAI --content reddit-claudeai

    # Monitor replies on your posts
    uv run python scripts/launch/reddit_helper.py monitor --poll 120

    # Dry run (print what would be posted)
    uv run python scripts/launch/reddit_helper.py post --subreddit ClaudeAI --content reddit-claudeai --dry-run
"""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime
from pathlib import Path

# Post content keyed by name
POSTS = {
    "reddit-claudeai": {
        "subreddit": "ClaudeAI",
        "title": "I built an open-source tool that analyzes your Claude Code session history — found 32% of my prompts were duplicates",
        "content_file": "docs/launch/reddit-posts.md",
        "section": "r/ClaudeAI",
    },
    "reddit-programming": {
        "subreddit": "programming",
        "title": "reprompt — CLI tool that extracts and deduplicates prompts from AI coding sessions using TF-IDF + SHA-256",
        "content_file": "docs/launch/reddit-posts.md",
        "section": "r/programming",
    },
    "reddit-localllama": {
        "subreddit": "LocalLLaMA",
        "title": "reprompt — analyze your AI coding prompts with TF-IDF dedup, supports Ollama embeddings for local-only semantic search",
        "content_file": "docs/launch/reddit-posts.md",
        "section": "r/LocalLLaMA",
    },
}

# Reply templates for common Reddit questions
REPLY_TEMPLATES = {
    "how_install": "Install with `pipx install reprompt-cli`, then `reprompt scan && reprompt report`. Zero config needed.",
    "what_tools": "Currently Claude Code and OpenClaw. Codex CLI, Aider, Gemini CLI planned. The adapter interface is ~20 lines if you want to add your tool.",
    "privacy": "100% local. Default TF-IDF uses scikit-learn, no network calls. Ollama embeddings optional for local GPU. Your data never leaves your machine.",
    "how_dedup": "Two layers: SHA-256 exact hash + TF-IDF cosine similarity (0.85 threshold). Catches both exact dupes and semantic near-dupes like 'fix auth bug' ≈ 'fix authentication issue'.",
    "vs_grep": "grep does keyword search. reprompt adds semantic dedup (TF-IDF cosine), pattern extraction, trend tracking, and an MCP server. The value is the pipeline, not any single feature.",
    "source": "MIT licensed, ~260 tests, strict mypy. GitHub: https://github.com/reprompt-dev/reprompt",
}


def extract_section(filepath: str, section_name: str) -> str:
    """Extract a section from a markdown file by ## header."""
    content = Path(filepath).read_text()
    lines = content.split("\n")
    in_section = False
    section_lines = []

    for line in lines:
        if line.startswith("## ") and section_name in line:
            in_section = True
            continue
        elif line.startswith("## ") and in_section:
            break
        elif in_section:
            section_lines.append(line)

    # Find the body after **Body:** or just return everything after title
    body_lines = []
    in_body = False
    for line in section_lines:
        if line.startswith("**Body:**") or line.startswith("**Body:**"):
            in_body = True
            continue
        elif line.startswith("---"):
            break
        elif in_body:
            body_lines.append(line)

    return "\n".join(body_lines).strip() if body_lines else "\n".join(section_lines).strip()


def post_to_reddit(subreddit: str, title: str, body: str, dry_run: bool = False) -> None:
    """Post to a subreddit."""
    if dry_run:
        print(f"[DRY RUN] Would post to r/{subreddit}:")
        print(f"  Title: {title}")
        print(f"  Body: {body[:200]}...")
        return

    import praw

    reddit = praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        username=os.environ["REDDIT_USERNAME"],
        password=os.environ["REDDIT_PASSWORD"],
        user_agent="reprompt-launch-helper/1.0",
    )

    sub = reddit.subreddit(subreddit)
    submission = sub.submit(title=title, selftext=body)
    print(f"Posted to r/{subreddit}: https://reddit.com{submission.permalink}")


def monitor_replies(poll_interval: int = 120) -> None:
    """Monitor replies on your recent posts."""
    import praw

    reddit = praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        username=os.environ["REDDIT_USERNAME"],
        password=os.environ["REDDIT_PASSWORD"],
        user_agent="reprompt-launch-helper/1.0",
    )

    seen_ids: set[str] = set()
    print(f"Monitoring replies. Polling every {poll_interval}s. Ctrl+C to stop.\n")

    while True:
        try:
            for comment in reddit.inbox.comment_replies(limit=25):
                if comment.id not in seen_ids:
                    seen_ids.add(comment.id)
                    ts = datetime.fromtimestamp(comment.created_utc).strftime("%H:%M")
                    print(f"\n[{ts}] u/{comment.author} replied:")
                    print(f"  {comment.body[:300]}")

                    # Suggest reply
                    body_lower = comment.body.lower()
                    for key, template in REPLY_TEMPLATES.items():
                        if any(word in body_lower for word in key.split("_")):
                            print(f"\n  SUGGESTED REPLY [{key}]:")
                            print(f"  {template}")
                            break
                    print()

            time.sleep(poll_interval)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(poll_interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reddit launch helper")
    sub = parser.add_subparsers(dest="command")

    post_cmd = sub.add_parser("post", help="Post to a subreddit")
    post_cmd.add_argument("--subreddit", required=True)
    post_cmd.add_argument("--content", required=True, choices=list(POSTS.keys()))
    post_cmd.add_argument("--dry-run", action="store_true")

    mon_cmd = sub.add_parser("monitor", help="Monitor replies")
    mon_cmd.add_argument("--poll", type=int, default=120)

    args = parser.parse_args()

    if args.command == "post":
        post_info = POSTS[args.content]
        body = extract_section(post_info["content_file"], post_info["section"])
        post_to_reddit(
            subreddit=args.subreddit,
            title=post_info["title"],
            body=body,
            dry_run=args.dry_run,
        )
    elif args.command == "monitor":
        monitor_replies(args.poll)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

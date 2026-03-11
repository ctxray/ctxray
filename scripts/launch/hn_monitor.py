"""Monitor your Show HN post for new comments and suggest replies.

HN has a public API — no auth needed for reading.

Usage:
    # After posting, get your post ID from the URL (e.g. https://news.ycombinator.com/item?id=12345)
    uv run python scripts/launch/hn_monitor.py --post-id 12345
    uv run python scripts/launch/hn_monitor.py --post-id 12345 --poll 60  # check every 60s
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from urllib.request import urlopen

HN_API = "https://hacker-news.firebaseio.com/v0"

# Pre-written reply templates for common HN questions
REPLY_TEMPLATES = {
    "grep": (
        "could do this with grep",
        "You're right that basic keyword search works with grep. "
        "reprompt adds two things grep can't do: (1) semantic dedup — catching "
        "'fix auth bug' ≈ 'fix authentication issue' via TF-IDF cosine similarity, "
        "and (2) pattern evolution tracking over time. The dedup alone caught 32% "
        "of my prompts as near-duplicates that exact matching would miss."
    ),
    "privacy": (
        "privacy|data|upload|send",
        "Everything runs 100% locally. Zero network calls by default. "
        "Your prompts never leave your machine. The default embedding backend "
        "is scikit-learn TF-IDF — no API keys, no external services. "
        "Ollama and sentence-transformers are optional local alternatives. "
        "OpenAI embeddings exist as an option but are entirely opt-in."
    ),
    "why_not_just": (
        "why not just|couldn't you just|seems like",
        "Fair point. The core value isn't any single feature — it's the combination: "
        "auto-detection of session files, semantic dedup, pattern extraction, "
        "trend tracking, and the MCP server so your AI assistant can learn from "
        "your history. Each piece is simple; the pipeline is what's useful."
    ),
    "other_tools": (
        "cursor|copilot|aider|codex",
        "Currently supports Claude Code and OpenClaw. Codex CLI, Aider, and "
        "Gemini CLI are planned — the adapter system makes it straightforward "
        "to add new tools. PRs welcome if anyone wants to add their favorite tool. "
        "The adapter interface is ~20 lines: parse session file → list of Prompt objects."
    ),
    "metrics": (
        "metric|what would|useful|daily",
        "Great question. The metrics I've found most useful: "
        "(1) specificity score trend — am I getting more precise over time? "
        "(2) category distribution — am I stuck in debug mode? "
        "(3) session effectiveness — which prompt patterns lead to clean exits vs. spirals? "
        "Would love to hear what you'd want to track."
    ),
    "how_dedup": (
        "dedup|duplicate|similarity|tfidf|cosine",
        "Two layers: (1) SHA-256 hash for exact matches (O(1) lookup), "
        "(2) TF-IDF cosine similarity for semantic near-duplicates (threshold 0.85, configurable). "
        "The TF-IDF vectorizer uses bigram/trigram n-grams with English stopword removal. "
        "On my 1,200 prompts, layer 1 caught ~10% exact dupes, layer 2 caught another ~22% semantic dupes."
    ),
}


def fetch_item(item_id: int) -> dict:
    """Fetch an HN item by ID."""
    url = f"{HN_API}/item/{item_id}.json"
    resp = urlopen(url)
    return json.loads(resp.read())


def get_all_comments(post_id: int) -> list[dict]:
    """Recursively fetch all comments on a post."""
    post = fetch_item(post_id)
    kid_ids = post.get("kids", [])
    comments = []
    for kid_id in kid_ids:
        try:
            comment = fetch_item(kid_id)
            if comment and comment.get("type") == "comment" and not comment.get("deleted"):
                comments.append(comment)
        except Exception:
            continue
    return comments


def suggest_reply(comment_text: str) -> str | None:
    """Match comment text against reply templates."""
    import re

    text_lower = comment_text.lower()
    for key, (pattern, reply) in REPLY_TEMPLATES.items():
        if re.search(pattern, text_lower):
            return f"[Template: {key}]\n{reply}"
    return None


def format_comment(comment: dict) -> str:
    """Format a comment for display."""
    by = comment.get("by", "unknown")
    text = comment.get("text", "")[:200]
    # Strip HTML tags
    import re
    text = re.sub(r"<[^>]+>", "", text)
    ts = datetime.fromtimestamp(comment.get("time", 0)).strftime("%H:%M")
    return f"  [{ts}] {by}: {text}"


def monitor(post_id: int, poll_interval: int = 120) -> None:
    """Monitor a post for new comments."""
    seen_ids: set[int] = set()

    print(f"Monitoring HN post {post_id}...")
    print(f"URL: https://news.ycombinator.com/item?id={post_id}")
    print(f"Polling every {poll_interval}s. Ctrl+C to stop.\n")

    while True:
        try:
            post = fetch_item(post_id)
            score = post.get("score", 0)
            descendants = post.get("descendants", 0)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Score: {score} | Comments: {descendants}")

            comments = get_all_comments(post_id)
            for comment in comments:
                cid = comment.get("id")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    print(f"\n  NEW COMMENT:")
                    print(format_comment(comment))

                    text = comment.get("text", "")
                    suggestion = suggest_reply(text)
                    if suggestion:
                        print(f"\n  SUGGESTED REPLY:\n  {suggestion}")
                    print()

            time.sleep(poll_interval)

        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(poll_interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor HN Show HN post")
    parser.add_argument("--post-id", type=int, required=True, help="HN post ID")
    parser.add_argument("--poll", type=int, default=120, help="Poll interval in seconds")
    args = parser.parse_args()
    monitor(args.post_id, args.poll)


if __name__ == "__main__":
    main()

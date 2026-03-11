"""Generate demo session data from CodeAlpaca-20K for reprompt demo recording.

Downloads coding prompts from HuggingFace and writes them as Claude Code
JSONL session files that reprompt can scan.

Usage:
    uv run python scripts/generate_demo_data.py [--count 800] [--output /tmp/reprompt-demo]
"""

from __future__ import annotations

import argparse
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import urlopen

HF_URL = (
    "https://huggingface.co/datasets/sahil2801/CodeAlpaca-20k"
    "/resolve/main/code_alpaca_20k.json"
)

PROJECTS = [
    "web-app",
    "api-service",
    "data-pipeline",
    "ml-trainer",
    "cli-tool",
    "auth-module",
    "dashboard",
    "payment-service",
    "search-engine",
    "chat-bot",
]

# Realistic near-duplicate prompts that developers actually repeat.
# Grouped by intent — reprompt's dedup should catch these.
REALISTIC_DUPES = [
    # Debug patterns (short, vague — typical real-world debug prompts)
    "Fix the failing unit test in the auth module",
    "Fix the broken test in the authentication module",
    "Fix the auth module unit test that's failing",
    "Fix this test failure",
    "Why is this test failing?",
    "The tests are broken, can you fix them?",
    "Debug the failing test in user service",
    "Debug the test failure in user service",
    # Test patterns
    "Add unit tests for the user registration endpoint",
    "Write tests for the user signup API endpoint",
    "Add test coverage for user registration",
    "Add tests for the login flow",
    "Write unit tests for the login endpoint",
    "Add test coverage for authentication",
    "Write integration tests for the payment flow",
    "Add integration tests for the payment service",
    # Refactor patterns
    "Refactor the database connection to use connection pooling",
    "Refactor the DB connection layer to implement connection pooling",
    "Refactor database connections to use a pool",
    "Refactor this function to be more readable",
    "Clean up this code and make it more maintainable",
    "Refactor the error handling in this module",
    "Refactor error handling to use custom exceptions",
    # Implement patterns
    "Add a REST endpoint for user profile updates",
    "Create an API endpoint to update user profiles",
    "Implement the user profile update endpoint",
    "Add pagination to the search results",
    "Implement pagination for the search API",
    "Add cursor-based pagination to search results",
    "Implement rate limiting for the API",
    "Add rate limiting middleware to the API endpoints",
    # Explain patterns
    "Explain how the caching middleware works",
    "Explain the caching middleware implementation",
    "How does the caching middleware work?",
    "Explain the authentication flow in this codebase",
    "How does the auth system work?",
    "Walk me through the authentication flow",
    # Review patterns
    "Review this PR for security issues",
    "Check this code for security vulnerabilities",
    "Review this pull request for potential security problems",
    "Is there anything wrong with this approach?",
    "Review my implementation and suggest improvements",
    # Config patterns
    "Set up the CI/CD pipeline for this project",
    "Configure GitHub Actions for automated testing",
    "Add a Dockerfile for the API service",
    "Create a Docker Compose configuration for local dev",
]


def fetch_prompts(count: int) -> list[str]:
    """Fetch coding prompts from CodeAlpaca-20K via HuggingFace."""
    print(f"Fetching {count} prompts from CodeAlpaca-20K...")
    resp = urlopen(HF_URL)
    data = json.loads(resp.read())
    prompts = [r["instruction"] for r in data if r.get("instruction")]
    # Filter: keep prompts > 20 chars, skip trivial ones
    prompts = [p for p in prompts if len(p) > 20]
    random.shuffle(prompts)
    return prompts[:count]


def write_sessions(
    prompts: list[str], output_dir: Path, n_weeks: int = 8, sessions_per_week: int = 15
) -> None:
    """Write prompts as Claude Code JSONL session files spread over n_weeks.

    Creates a realistic timeline so `reprompt trends` shows meaningful evolution.
    Earlier weeks have shorter/vaguer prompts, later weeks have longer/specific ones.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for proj in PROJECTS:
        (output_dir / proj).mkdir(exist_ok=True)

    base_time = datetime(2026, 1, 13, 8, 0, 0)  # Monday week 1
    prompt_idx = 0
    total_sessions = 0

    for week in range(n_weeks):
        week_start = base_time + timedelta(weeks=week)
        n_sessions = sessions_per_week + random.randint(-3, 5)  # 12-20 sessions/week

        for s in range(n_sessions):
            remaining = len(prompts) - prompt_idx
            if remaining < 3:
                break

            project = random.choice(PROJECTS)
            session_id = str(uuid.uuid4())[:8]
            session_file = output_dir / project / f"{session_id}.jsonl"

            # Sessions get longer in later weeks (users become more productive)
            min_p = 3 + week // 2
            max_p = min(8 + week, remaining)
            if max_p < min_p:
                break
            n_prompts = random.randint(min_p, max_p)

            # Random time within the week (business hours bias)
            day_offset = random.randint(0, 4)  # Mon-Fri
            hour = random.choice([9, 10, 11, 13, 14, 15, 16, 17])  # work hours
            session_time = week_start + timedelta(days=day_offset, hours=hour)

            tool_names = ["Edit", "Write", "Read", "Bash", "Grep", "Glob"]
            error_phrases = ["Error:", "Traceback", "failed", "TypeError", "ImportError"]

            with open(session_file, "w") as f:
                for j in range(n_prompts):
                    ts = (session_time + timedelta(minutes=j * random.randint(2, 8))).isoformat() + "Z"

                    entry = {
                        "type": "user",
                        "timestamp": ts,
                        "message": {"role": "user", "content": prompts[prompt_idx]},
                    }
                    f.write(json.dumps(entry) + "\n")

                    # Realistic assistant response with tool use
                    n_tools = random.randint(1, 4)
                    content_blocks = [
                        {"type": "text", "text": "I'll help with that."},
                    ]
                    for t in range(n_tools):
                        content_blocks.append(
                            {"type": "tool_use", "name": random.choice(tool_names), "id": f"t_{j}_{t}"}
                        )

                    # Occasional errors in assistant responses (for effectiveness scoring)
                    if random.random() < 0.1:
                        content_blocks[0]["text"] += f" {random.choice(error_phrases)}: something went wrong"

                    assistant_ts = (session_time + timedelta(minutes=j * 3 + 2)).isoformat() + "Z"
                    assistant_entry = {
                        "type": "assistant",
                        "timestamp": assistant_ts,
                        "message": {"role": "assistant", "content": content_blocks},
                    }
                    f.write(json.dumps(assistant_entry) + "\n")

                    prompt_idx += 1

            total_sessions += 1

    print(f"Wrote {prompt_idx} prompts across {total_sessions} sessions ({n_weeks} weeks) to {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate demo data for reprompt")
    parser.add_argument("--count", type=int, default=800, help="Number of prompts to fetch")
    parser.add_argument("--output", type=str, default="/tmp/reprompt-demo", help="Output directory")
    args = parser.parse_args()

    prompts = fetch_prompts(args.count)
    print(f"Got {len(prompts)} prompts from CodeAlpaca-20K")

    # Sprinkle realistic duplicates throughout (repeat each 2-4 times)
    dupes_with_repeats = []
    for p in REALISTIC_DUPES:
        dupes_with_repeats.extend([p] * random.randint(2, 4))
    random.shuffle(dupes_with_repeats)

    # Interleave dupes throughout the prompt list
    combined = []
    dupe_idx = 0
    for i, p in enumerate(prompts):
        combined.append(p)
        # Insert a dupe every ~8 prompts
        if i % 8 == 0 and dupe_idx < len(dupes_with_repeats):
            combined.append(dupes_with_repeats[dupe_idx])
            dupe_idx += 1
    # Append remaining dupes
    combined.extend(dupes_with_repeats[dupe_idx:])

    print(f"Total prompts (with {len(dupes_with_repeats)} duplicate insertions): {len(combined)}")
    write_sessions(combined, Path(args.output))


if __name__ == "__main__":
    main()

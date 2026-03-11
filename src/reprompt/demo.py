"""Generate demo data for `reprompt demo` — no network required."""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

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

# Realistic near-duplicate prompts grouped by intent.
REALISTIC_PROMPTS = [
    # Debug (short, vague)
    "Fix the failing unit test in the auth module",
    "Fix the broken test in the authentication module",
    "Fix the auth module unit test that's failing",
    "Fix this test failure",
    "Why is this test failing?",
    "The tests are broken, can you fix them?",
    "Debug the failing test in user service",
    "Debug the test failure in user service",
    # Test
    "Add unit tests for the user registration endpoint",
    "Write tests for the user signup API endpoint",
    "Add test coverage for user registration",
    "Add tests for the login flow",
    "Write unit tests for the login endpoint",
    "Add test coverage for authentication",
    "Write integration tests for the payment flow",
    "Add integration tests for the payment service",
    # Refactor
    "Refactor the database connection to use connection pooling",
    "Refactor the DB connection layer to implement connection pooling",
    "Refactor database connections to use a pool",
    "Refactor this function to be more readable",
    "Clean up this code and make it more maintainable",
    "Refactor the error handling in this module",
    "Refactor error handling to use custom exceptions",
    # Implement
    "Add a REST endpoint for user profile updates",
    "Create an API endpoint to update user profiles",
    "Implement the user profile update endpoint",
    "Add pagination to the search results",
    "Implement pagination for the search API",
    "Add cursor-based pagination to search results",
    "Implement rate limiting for the API",
    "Add rate limiting middleware to the API endpoints",
    "Implement WebSocket support for real-time notifications",
    "Add WebSocket connection handling for live updates",
    "Create a middleware for request logging",
    "Add request/response logging middleware",
    "Implement JWT token refresh endpoint",
    "Add token refresh logic to the auth service",
    # Explain
    "Explain how the caching middleware works",
    "Explain the caching middleware implementation",
    "How does the caching middleware work?",
    "Explain the authentication flow in this codebase",
    "How does the auth system work?",
    "Walk me through the authentication flow",
    "What does this regex do?",
    "Explain what this regular expression matches",
    # Review
    "Review this PR for security issues",
    "Check this code for security vulnerabilities",
    "Review this pull request for potential security problems",
    "Is there anything wrong with this approach?",
    "Review my implementation and suggest improvements",
    "Check this function for edge cases I might have missed",
    "Review the error handling in this module",
    # Config
    "Set up the CI/CD pipeline for this project",
    "Configure GitHub Actions for automated testing",
    "Add a Dockerfile for the API service",
    "Create a Docker Compose configuration for local dev",
    "Set up pre-commit hooks for linting",
    "Configure ESLint and Prettier for the project",
    # Additional variety
    "How do I handle file uploads in this API?",
    "Add input validation for the create user endpoint",
    "Implement soft delete for the user model",
    "Add database migration for the new schema",
    "Create a health check endpoint",
    "Add structured logging to the application",
    "Implement retry logic for external API calls",
    "Add caching to the frequently-queried endpoints",
    "Write a script to seed the database with test data",
    "Optimize the database queries in the dashboard module",
    "Add error boundary components to the React frontend",
    "Implement proper CORS configuration",
    "Add API versioning to the REST endpoints",
    "Create a CLI command for database backup",
    "Implement graceful shutdown handling",
    "Add OpenAPI documentation to the API",
    "Write a data migration script for the schema change",
    "Implement batch processing for the import endpoint",
    "Add rate limiting per user for the public API",
    "Create an admin dashboard with usage metrics",
]


def generate_demo_sessions(output_dir: Path, n_weeks: int = 6) -> int:
    """Generate demo session files. Returns number of prompts written."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for proj in PROJECTS:
        (output_dir / proj).mkdir(exist_ok=True)

    # Build prompt list with realistic duplication
    prompts: list[str] = []
    for p in REALISTIC_PROMPTS:
        copies = random.randint(1, 3)
        prompts.extend([p] * copies)
    random.shuffle(prompts)

    base_time = datetime(2026, 1, 13, 8, 0, 0)
    prompt_idx = 0
    total_sessions = 0

    for week in range(n_weeks):
        week_start = base_time + timedelta(weeks=week)
        n_sessions = 12 + random.randint(0, 6)

        for _ in range(n_sessions):
            remaining = len(prompts) - prompt_idx
            if remaining < 3:
                break

            project = random.choice(PROJECTS)
            session_id = str(uuid.uuid4())[:8]
            session_file = output_dir / project / f"{session_id}.jsonl"

            min_p = 3 + week // 2
            max_p = min(6 + week, remaining)
            if max_p < min_p:
                break
            n_prompts = random.randint(min_p, max_p)

            day_offset = random.randint(0, 4)
            hour = random.choice([9, 10, 11, 13, 14, 15, 16, 17])
            session_time = week_start + timedelta(days=day_offset, hours=hour)

            tool_names = ["Edit", "Write", "Read", "Bash", "Grep", "Glob"]
            error_phrases = ["Error:", "Traceback", "failed", "TypeError", "ImportError"]

            with open(session_file, "w") as f:
                for j in range(n_prompts):
                    ts = (
                        session_time + timedelta(minutes=j * random.randint(2, 8))
                    ).isoformat() + "Z"

                    entry = {
                        "type": "user",
                        "timestamp": ts,
                        "message": {"role": "user", "content": prompts[prompt_idx]},
                    }
                    f.write(json.dumps(entry) + "\n")

                    n_tools = random.randint(1, 4)
                    content_blocks = [{"type": "text", "text": "I'll help with that."}]
                    for t in range(n_tools):
                        tool = random.choice(tool_names)
                        content_blocks.append(
                            {"type": "tool_use", "name": tool, "id": f"t_{j}_{t}"}
                        )
                    if random.random() < 0.1:
                        content_blocks[0]["text"] += (
                            f" {random.choice(error_phrases)}: something went wrong"
                        )

                    assistant_ts = (session_time + timedelta(minutes=j * 3 + 2)).isoformat() + "Z"
                    assistant_entry = {
                        "type": "assistant",
                        "timestamp": assistant_ts,
                        "message": {"role": "assistant", "content": content_blocks},
                    }
                    f.write(json.dumps(assistant_entry) + "\n")

                    prompt_idx += 1

            total_sessions += 1

    return prompt_idx

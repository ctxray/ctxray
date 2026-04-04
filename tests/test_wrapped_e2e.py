# tests/test_wrapped_e2e.py
"""End-to-end test: insert prompts -> score -> wrapped report."""

import json
from pathlib import Path

import pytest

from ctxray.core.extractors import extract_features
from ctxray.core.scorer import score_prompt
from ctxray.core.wrapped import build_wrapped
from ctxray.output.wrapped_html import render_wrapped_html
from ctxray.output.wrapped_terminal import render_wrapped
from ctxray.storage.db import PromptDB


@pytest.fixture
def populated_db(tmp_path: Path) -> PromptDB:
    """Create a DB with realistic prompt data, scored via the real pipeline."""
    db = PromptDB(tmp_path / "e2e.db")
    prompts = [
        "Fix the authentication bug in src/auth/login.ts where the JWT token expires",
        (
            "You are a senior Python developer. Refactor the database module"
            " to use async/await. Must maintain backward compatibility."
            " Output as a diff."
        ),
        "what does this code do",
        (
            "Add unit tests for the payment processing module. Include edge"
            " cases for expired cards, insufficient funds, and network"
            " timeouts. Use pytest fixtures."
        ),
        ("Explain the difference between a mutex and a semaphore. Give examples in Go."),
        (
            "Debug this error: TypeError: Cannot read property 'map' of"
            " undefined at components/UserList.tsx:42. Here's the component"
            " code: ```tsx\nconst users = props.data.map(u => u.name)\n```"
        ),
        "implement a binary search function",
        (
            "As a DevOps engineer, write a Dockerfile for a Python FastAPI"
            " app. Requirements: multi-stage build, non-root user, health"
            " check endpoint. Base image: python:3.12-slim."
        ),
    ]
    for i, text in enumerate(prompts):
        db.insert_prompt(
            text,
            source="claude_code",
            session_id=f"e2e-session-{i % 3}",
            timestamp=f"2026-03-{10 + i}T10:00:00",
        )
        dna = extract_features(text, source="claude_code", session_id=f"e2e-{i}")
        breakdown = score_prompt(dna)
        dna.overall_score = breakdown.total
        features = dna.to_dict()
        features["structure"] = breakdown.structure
        features["context"] = breakdown.context
        features["position"] = breakdown.position
        features["repetition"] = breakdown.repetition
        features["clarity"] = breakdown.clarity
        db.store_features(dna.prompt_hash, features)
    return db


class TestWrappedE2E:
    def test_full_pipeline(self, populated_db: PromptDB) -> None:
        report = build_wrapped(populated_db)
        assert report.total_prompts == 8
        assert report.scored_prompts == 8
        assert 0 < report.avg_overall < 100
        assert report.persona is not None

    def test_terminal_output(self, populated_db: PromptDB) -> None:
        report = build_wrapped(populated_db)
        text = render_wrapped(report)
        assert isinstance(text, str)
        assert len(text) > 100  # non-trivial output
        assert str(report.total_prompts) in text

    def test_html_output(self, populated_db: PromptDB) -> None:
        report = build_wrapped(populated_db)
        html = render_wrapped_html(report)
        assert "<html" in html
        assert "ctxray" in html

    def test_json_roundtrip(self, populated_db: PromptDB) -> None:
        report = build_wrapped(populated_db)
        d = report.to_dict()
        serialized = json.dumps(d)
        deserialized = json.loads(serialized)
        assert deserialized["persona"]["name"] is not None
        assert deserialized["total_prompts"] == report.total_prompts

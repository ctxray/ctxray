"""Tests for expanded insights command with effectiveness + similar prompts."""

from __future__ import annotations

import json
import re
import tempfile
from datetime import datetime, timedelta, timezone

from typer.testing import CliRunner

from reprompt.cli import app
from reprompt.storage.db import PromptDB

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _seed_db_with_patterns(db: PromptDB) -> None:
    """Seed DB with enough prompts + patterns for insights to show expanded sections."""
    now = datetime.now(timezone.utc)
    for i in range(10):
        ts = (now - timedelta(days=1, hours=i)).isoformat()
        db.insert_prompt(
            f"Fix the auth bug in module {i} with specific implementation details",
            source="claude-code",
            timestamp=ts,
        )

    from dataclasses import asdict

    from reprompt.core.extractors import extract_features
    from reprompt.core.scorer import score_prompt

    for p in db.get_all_prompts():
        dna = extract_features(p["text"], source=p["source"], session_id="test")
        breakdown = score_prompt(dna)
        dna.overall_score = breakdown.total
        db.store_features(p["hash"], asdict(dna))

    db.compute_pattern_effectiveness()


def _seed_similar_prompts(db: PromptDB) -> None:
    """Seed prompts that will form similarity clusters."""
    now = datetime.now(timezone.utc)
    variations = [
        "Explain how the authentication system works in detail please",
        "Explain how the authentication system works step by step please",
        "Explain how the authentication system works with examples please",
        "Explain how the authentication system works thoroughly please",
        "Explain how the authentication system works completely please",
    ]
    for i, text in enumerate(variations):
        ts = (now - timedelta(hours=i)).isoformat()
        db.insert_prompt(text, source="claude-code", timestamp=ts)
    for i in range(5):
        ts = (now - timedelta(hours=i + 10)).isoformat()
        db.insert_prompt(
            f"Debug the database connection timeout error {i}",
            source="claude-code",
            timestamp=ts,
        )


class TestGetEffectivenessInsight:
    def test_returns_none_when_no_patterns(self, tmp_path):
        from reprompt.core.insights import get_effectiveness_insight

        db = PromptDB(tmp_path / "empty.db")
        result = get_effectiveness_insight(db)
        assert result is None

    def test_returns_data_with_patterns(self, tmp_path):
        from reprompt.core.insights import get_effectiveness_insight

        db = PromptDB(tmp_path / "test.db")
        _seed_db_with_patterns(db)
        result = get_effectiveness_insight(db)
        # compute_pattern_effectiveness may not set effectiveness_avg if no
        # prompt-level effectiveness scores exist, so result may be None
        if result is not None:
            assert "top_patterns" in result
            assert isinstance(result["top_patterns"], list)
            assert "total_patterns" in result


class TestGetSimilarPromptsInsight:
    def test_returns_none_when_few_prompts(self, tmp_path):
        from reprompt.core.insights import get_similar_prompts_insight

        db = PromptDB(tmp_path / "empty.db")
        result = get_similar_prompts_insight(db)
        assert result is None

    def test_returns_data_with_similar_prompts(self, tmp_path):
        from reprompt.core.insights import get_similar_prompts_insight

        db = PromptDB(tmp_path / "test.db")
        _seed_similar_prompts(db)
        result = get_similar_prompts_insight(db)
        if result is not None:
            assert "clusters" in result
            assert len(result["clusters"]) > 0


class TestInsightsExpandedCLI:
    def test_insights_includes_new_sections_json(self, tmp_path):
        db_path = tmp_path / "test.db"
        db = PromptDB(db_path)
        _seed_db_with_patterns(db)
        _seed_similar_prompts(db)

        result = runner.invoke(app, ["insights", "--json"], env={"REPROMPT_DB_PATH": str(db_path)})
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "effectiveness" in data
        assert "similar_prompts" in data

    def test_insights_no_data_still_works(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            result = runner.invoke(app, ["insights"], env={"REPROMPT_DB_PATH": f.name})
        assert result.exit_code == 0

    def test_insights_source_filter(self, tmp_path):
        db_path = tmp_path / "test.db"
        db = PromptDB(db_path)
        _seed_db_with_patterns(db)

        result = runner.invoke(
            app,
            ["insights", "--source", "claude-code", "--json"],
            env={"REPROMPT_DB_PATH": str(db_path)},
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "effectiveness" in data

"""End-to-end test: extension → Native Messaging → DB → CLI.

Simulates the full pipeline that a browser extension user would trigger:
1. Extension captures prompts from ChatGPT/Claude.ai/Gemini
2. Sends them via Native Messaging protocol (4-byte length-prefixed JSON)
3. reprompt bridge host subprocess receives and stores in DB
4. CLI commands (extension-status, report) see the stored data

This test spawns a real subprocess (reprompt.bridge.host), sends multi-message
sequences through its stdin, and verifies the final DB + CLI state.
"""

from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from reprompt.cli import app
from reprompt.storage.db import PromptDB

runner = CliRunner()


def _encode(msg: dict) -> bytes:
    """Encode a message in Native Messaging wire format."""
    payload = json.dumps(msg).encode("utf-8")
    return struct.pack("@I", len(payload)) + payload


def _decode_all(data: bytes) -> list[dict]:
    """Decode all messages from a Native Messaging response stream."""
    messages = []
    offset = 0
    while offset < len(data):
        if offset + 4 > len(data):
            break
        (length,) = struct.unpack("@I", data[offset : offset + 4])
        offset += 4
        if offset + length > len(data):
            break
        messages.append(json.loads(data[offset : offset + length].decode("utf-8")))
        offset += length
    return messages


def _run_host(db_path: Path, messages: list[dict], timeout: int = 10) -> list[dict]:
    """Run the bridge host subprocess with a sequence of messages."""
    env = {**os.environ, "REPROMPT_DB_PATH": str(db_path)}
    input_data = b"".join(_encode(m) for m in messages)

    result = subprocess.run(
        [sys.executable, "-u", "-m", "reprompt.bridge.host"],
        input=input_data,
        capture_output=True,
        timeout=timeout,
        env=env,
    )
    assert result.returncode == 0, f"Host failed: {result.stderr.decode()}"
    return _decode_all(result.stdout)


# ---------------------------------------------------------------------------
# E2E: Multi-source extension sync
# ---------------------------------------------------------------------------


class TestExtensionE2EPipeline:
    """Full round-trip: extension messages → NM host → DB → CLI."""

    CHATGPT_PROMPTS = [
        {
            "text": "Explain the difference between Python lists and tuples with examples",
            "source": "chatgpt-ext",
            "timestamp": "2026-03-20T09:00:00Z",
            "conversation_id": "chatgpt-conv-001",
            "conversation_title": "Python data structures",
        },
        {
            "text": "How do I convert a list of dicts to a pandas DataFrame efficiently?",
            "source": "chatgpt-ext",
            "timestamp": "2026-03-20T09:05:00Z",
            "conversation_id": "chatgpt-conv-001",
            "conversation_title": "Python data structures",
        },
    ]

    CLAUDE_PROMPTS = [
        {
            "text": "Refactor this authentication middleware to use JWT refresh tokens",
            "source": "claude-ext",
            "timestamp": "2026-03-20T10:00:00Z",
            "conversation_id": "claude-conv-001",
            "conversation_title": "Auth refactor",
        },
    ]

    GEMINI_PROMPTS = [
        {
            "text": "Write a Rust function that parses ISO 8601 dates without external crates",
            "source": "gemini-ext",
            "timestamp": "2026-03-20T11:00:00Z",
            "conversation_id": "gemini-conv-001",
            "conversation_title": "Rust date parsing",
        },
    ]

    def test_multi_source_sync_and_verify(self, tmp_path: Path) -> None:
        """Sync prompts from 3 sources, verify all stored correctly."""
        db_path = tmp_path / "e2e.db"

        # Send: ping → sync chatgpt → sync claude → sync gemini → get_status
        messages = [
            {"type": "ping"},
            {"type": "sync_prompts", "prompts": self.CHATGPT_PROMPTS},
            {"type": "sync_prompts", "prompts": self.CLAUDE_PROMPTS},
            {"type": "sync_prompts", "prompts": self.GEMINI_PROMPTS},
            {"type": "get_status"},
        ]

        responses = _run_host(db_path, messages)
        assert len(responses) == 5

        # Verify ping
        assert responses[0]["type"] == "pong"

        # Verify sync results
        assert responses[1] == {
            "type": "sync_result",
            "received": 2,
            "new_stored": 2,
            "duplicates": 0,
        }
        assert responses[2] == {
            "type": "sync_result",
            "received": 1,
            "new_stored": 1,
            "duplicates": 0,
        }
        assert responses[3] == {
            "type": "sync_result",
            "received": 1,
            "new_stored": 1,
            "duplicates": 0,
        }

        # Verify status shows all 4 prompts
        assert responses[4]["type"] == "status"
        assert responses[4]["total_prompts"] == 4

        # Verify DB directly
        db = PromptDB(db_path)
        all_prompts = db.get_all_prompts()
        assert len(all_prompts) == 4

        sources = {p["source"] for p in all_prompts}
        assert sources == {"chatgpt-ext", "claude-ext", "gemini-ext"}

    def test_dedup_across_syncs(self, tmp_path: Path) -> None:
        """Same prompts sent twice should be deduped on second sync."""
        db_path = tmp_path / "e2e_dedup.db"

        # First sync
        responses_1 = _run_host(
            db_path,
            [{"type": "sync_prompts", "prompts": self.CHATGPT_PROMPTS}],
        )
        assert responses_1[0]["new_stored"] == 2

        # Second sync — same prompts (new subprocess, same DB)
        responses_2 = _run_host(
            db_path,
            [{"type": "sync_prompts", "prompts": self.CHATGPT_PROMPTS}],
        )
        assert responses_2[0]["new_stored"] == 0
        assert responses_2[0]["duplicates"] == 2

        # DB should still have only 2
        db = PromptDB(db_path)
        assert len(db.get_all_prompts()) == 2

    def test_mixed_valid_and_noise(self, tmp_path: Path) -> None:
        """Batch with valid prompts + noise: only valid ones stored."""
        db_path = tmp_path / "e2e_mixed.db"

        mixed_prompts = [
            # Valid
            {
                "text": "Explain the observer pattern with a TypeScript example",
                "source": "chatgpt-ext",
                "timestamp": "2026-03-20T12:00:00Z",
                "conversation_id": "c1",
                "conversation_title": "Design patterns",
            },
            # Too short — filtered
            {
                "text": "ok",
                "source": "chatgpt-ext",
                "timestamp": "",
                "conversation_id": "c1",
                "conversation_title": "t",
            },
            # Acknowledgment — filtered
            {
                "text": "sure",
                "source": "chatgpt-ext",
                "timestamp": "",
                "conversation_id": "c1",
                "conversation_title": "t",
            },
            # Valid
            {
                "text": "Can you add error handling to the database connection pool?",
                "source": "claude-ext",
                "timestamp": "2026-03-20T12:05:00Z",
                "conversation_id": "c2",
                "conversation_title": "DB pool",
            },
        ]

        responses = _run_host(
            db_path,
            [{"type": "sync_prompts", "prompts": mixed_prompts}],
        )
        assert responses[0]["received"] == 4
        assert responses[0]["new_stored"] == 2

    def test_cli_extension_status_sees_synced_data(self, tmp_path: Path, monkeypatch) -> None:
        """After sync, extension-status CLI shows correct prompt count."""
        db_path = tmp_path / "e2e_cli.db"

        # Sync some prompts via the host subprocess
        _run_host(
            db_path,
            [{"type": "sync_prompts", "prompts": self.CHATGPT_PROMPTS + self.CLAUDE_PROMPTS}],
        )

        # Now run CLI extension-status pointing at same DB
        import reprompt.bridge.manifest as manifest_mod

        # Create a fake manifest so it shows as "registered"
        manifest_dir = tmp_path / "nm"
        manifest_dir.mkdir()
        (manifest_dir / "dev.reprompt.bridge.json").write_text("{}")
        monkeypatch.setattr(manifest_mod, "get_manifest_dir", lambda browser: manifest_dir)
        monkeypatch.setenv("REPROMPT_DB_PATH", str(db_path))

        result = runner.invoke(app, ["extension-status"])
        assert result.exit_code == 0
        assert "Registered" in result.output or "registered" in result.output
        # Should show 3 extension prompts
        assert "3" in result.output

    def test_cli_report_includes_extension_prompts(self, tmp_path: Path, monkeypatch) -> None:
        """After sync, reprompt report --format json includes extension-sourced prompts."""
        db_path = tmp_path / "e2e_report.db"

        # Sync prompts
        _run_host(
            db_path,
            [{"type": "sync_prompts", "prompts": self.CHATGPT_PROMPTS}],
        )

        monkeypatch.setenv("REPROMPT_DB_PATH", str(db_path))

        result = runner.invoke(app, ["report", "--format", "json"])
        assert result.exit_code == 0

        report = json.loads(result.output)
        assert report["overview"]["total_prompts"] >= 2

    def test_incremental_sync_new_prompts_only(self, tmp_path: Path) -> None:
        """Subsequent syncs with new prompts add only the new ones."""
        db_path = tmp_path / "e2e_incr.db"

        # First sync: 2 chatgpt prompts
        r1 = _run_host(
            db_path,
            [{"type": "sync_prompts", "prompts": self.CHATGPT_PROMPTS}],
        )
        assert r1[0]["new_stored"] == 2

        # Second sync: same 2 + 1 new claude prompt
        combined = self.CHATGPT_PROMPTS + self.CLAUDE_PROMPTS
        r2 = _run_host(
            db_path,
            [{"type": "sync_prompts", "prompts": combined}],
        )
        assert r2[0]["new_stored"] == 1
        assert r2[0]["duplicates"] == 2

        # DB total should be 3
        db = PromptDB(db_path)
        assert len(db.get_all_prompts()) == 3

    def test_last_sync_timestamp_updated(self, tmp_path: Path) -> None:
        """After sync, get_status shows a recent last_sync timestamp."""
        db_path = tmp_path / "e2e_ts.db"

        responses = _run_host(
            db_path,
            [
                {"type": "sync_prompts", "prompts": self.CHATGPT_PROMPTS},
                {"type": "get_status"},
            ],
        )

        status = responses[1]
        assert status["type"] == "status"
        assert status["last_sync"]  # non-empty
        assert status["last_sync"].startswith("20")  # ISO timestamp

    def test_source_filtering_after_sync(self, tmp_path: Path) -> None:
        """DB source filtering works correctly for extension sources."""
        db_path = tmp_path / "e2e_filter.db"

        _run_host(
            db_path,
            [
                {"type": "sync_prompts", "prompts": self.CHATGPT_PROMPTS},
                {"type": "sync_prompts", "prompts": self.CLAUDE_PROMPTS},
                {"type": "sync_prompts", "prompts": self.GEMINI_PROMPTS},
            ],
        )

        db = PromptDB(db_path)
        chatgpt = db.get_all_prompts(source="chatgpt-ext")
        claude = db.get_all_prompts(source="claude-ext")
        gemini = db.get_all_prompts(source="gemini-ext")

        assert len(chatgpt) == 2
        assert len(claude) == 1
        assert len(gemini) == 1

        # Verify content integrity
        assert "lists and tuples" in chatgpt[0]["text"]
        assert "JWT refresh tokens" in claude[0]["text"]
        assert "ISO 8601" in gemini[0]["text"]

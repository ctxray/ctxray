"""Integration test: host subprocess with real stdio protocol."""

from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
from pathlib import Path


def _encode_message(msg: dict) -> bytes:
    payload = json.dumps(msg).encode("utf-8")
    return struct.pack("@I", len(payload)) + payload


def _decode_message(data: bytes) -> dict:
    length = struct.unpack("@I", data[:4])[0]
    return json.loads(data[4 : 4 + length].decode("utf-8"))


def test_host_ping_pong(tmp_path: Path) -> None:
    """Send a ping message via subprocess and verify pong response."""
    db_path = tmp_path / "test.db"
    env = {**os.environ, "REPROMPT_DB_PATH": str(db_path)}

    # Send ping then close stdin
    input_data = _encode_message({"type": "ping"})

    result = subprocess.run(
        [sys.executable, "-u", "-m", "reprompt.bridge.host"],
        input=input_data,
        capture_output=True,
        timeout=10,
        env=env,
    )

    assert result.returncode == 0
    response = _decode_message(result.stdout)
    assert response["type"] == "pong"
    assert "version" in response


def test_host_sync_prompts(tmp_path: Path) -> None:
    """Send sync_prompts via subprocess and verify storage."""
    db_path = tmp_path / "test.db"
    env = {**os.environ, "REPROMPT_DB_PATH": str(db_path)}

    msg = {
        "type": "sync_prompts",
        "prompts": [
            {
                "text": "Explain how Python generators work with examples",
                "source": "chatgpt-ext",
                "timestamp": "2026-03-15T10:00:00Z",
                "conversation_id": "conv-001",
                "conversation_title": "Python generators",
            },
        ],
    }
    input_data = _encode_message(msg)

    result = subprocess.run(
        [sys.executable, "-u", "-m", "reprompt.bridge.host"],
        input=input_data,
        capture_output=True,
        timeout=10,
        env=env,
    )

    assert result.returncode == 0
    response = _decode_message(result.stdout)
    assert response["type"] == "sync_result"
    assert response["new_stored"] == 1

    # Verify prompt actually stored in DB
    from reprompt.storage.db import PromptDB

    db = PromptDB(db_path)
    stats = db.get_stats()
    assert stats["total_prompts"] >= 1

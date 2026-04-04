"""Tests for Native Messaging stdio protocol."""

from __future__ import annotations

import io
import json
import struct

from ctxray.bridge.protocol import read_message, write_message


def test_read_message_basic() -> None:
    """Read a length-prefixed JSON message from a binary stream."""
    payload = json.dumps({"type": "ping"}).encode("utf-8")
    header = struct.pack("@I", len(payload))
    stream = io.BytesIO(header + payload)
    msg = read_message(stream)
    assert msg == {"type": "ping"}


def test_read_message_unicode() -> None:
    """Read a message containing unicode characters."""
    payload = json.dumps({"type": "sync_prompts", "text": "修复登录问题"}).encode("utf-8")
    header = struct.pack("@I", len(payload))
    stream = io.BytesIO(header + payload)
    msg = read_message(stream)
    assert msg["text"] == "修复登录问题"


def test_read_message_eof() -> None:
    """Return None when stdin is closed (0 bytes read)."""
    stream = io.BytesIO(b"")
    msg = read_message(stream)
    assert msg is None


def test_read_message_incomplete_header() -> None:
    """Return None when header is incomplete (less than 4 bytes)."""
    stream = io.BytesIO(b"\x01\x02")
    msg = read_message(stream)
    assert msg is None


def test_write_message_basic() -> None:
    """Write a length-prefixed JSON message to a binary stream."""
    stream = io.BytesIO()
    write_message(stream, {"type": "pong", "version": "0.9.1"})
    stream.seek(0)
    header = stream.read(4)
    length = struct.unpack("@I", header)[0]
    payload = json.loads(stream.read(length).decode("utf-8"))
    assert payload["type"] == "pong"
    assert payload["version"] == "0.9.1"


def test_roundtrip() -> None:
    """Write then read should return the same message."""
    original = {"type": "sync_prompts", "prompts": [{"text": "hello", "source": "chatgpt-ext"}]}
    buf = io.BytesIO()
    write_message(buf, original)
    buf.seek(0)
    result = read_message(buf)
    assert result == original

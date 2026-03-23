"""Tests for ChatGPTAdapter.parse_conversation()."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from reprompt.adapters.chatgpt import ChatGPTAdapter

SAMPLE_EXPORT = [
    {
        "title": "Fix auth bug",
        "create_time": 1711180800.0,
        "mapping": {
            "root": {
                "id": "root",
                "message": None,
                "parent": None,
                "children": ["msg1"],
            },
            "msg1": {
                "id": "msg1",
                "message": {
                    "author": {"role": "user"},
                    "content": {"parts": ["Fix the auth bug in login.py"]},
                    "create_time": 1711180800.0,
                },
                "parent": "root",
                "children": ["msg2"],
            },
            "msg2": {
                "id": "msg2",
                "message": {
                    "author": {"role": "assistant"},
                    "content": {"parts": ["I'll fix the auth bug. Here's the change..."]},
                    "create_time": 1711180805.0,
                },
                "parent": "msg1",
                "children": ["msg3"],
            },
            "msg3": {
                "id": "msg3",
                "message": {
                    "author": {"role": "user"},
                    "content": {"parts": ["Now add tests"]},
                    "create_time": 1711180860.0,
                },
                "parent": "msg2",
                "children": ["msg4"],
            },
            "msg4": {
                "id": "msg4",
                "message": {
                    "author": {"role": "assistant"},
                    "content": {"parts": ["Here are the tests..."]},
                    "create_time": 1711180865.0,
                },
                "parent": "msg3",
                "children": [],
            },
        },
    },
    {
        "title": "Second conversation",
        "create_time": 1711190000.0,
        "mapping": {
            "root": {
                "id": "root",
                "message": None,
                "parent": None,
                "children": ["m1"],
            },
            "m1": {
                "id": "m1",
                "message": {
                    "author": {"role": "user"},
                    "content": {"parts": ["Hello"]},
                    "create_time": 1711190000.0,
                },
                "parent": "root",
                "children": [],
            },
        },
    },
]


def _write_json(data: list) -> Path:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, tmp)
    tmp.close()
    return Path(tmp.name)


def test_parse_conversation_returns_both_roles():
    path = _write_json(SAMPLE_EXPORT)
    adapter = ChatGPTAdapter()
    turns = adapter.parse_conversation(path)
    roles = {t.role for t in turns}
    assert roles == {"user", "assistant"}


def test_parse_conversation_first_conversation_by_default():
    path = _write_json(SAMPLE_EXPORT)
    adapter = ChatGPTAdapter()
    turns = adapter.parse_conversation(path)
    assert len(turns) == 4


def test_parse_conversation_conv_id_selection():
    path = _write_json(SAMPLE_EXPORT)
    adapter = ChatGPTAdapter()
    from reprompt.adapters.chatgpt import _make_session_id

    conv_id_2 = _make_session_id(SAMPLE_EXPORT[1])
    turns = adapter.parse_conversation(path, conv_id=conv_id_2)
    assert len(turns) == 1
    assert turns[0].text == "Hello"


def test_parse_conversation_chronological_order():
    path = _write_json(SAMPLE_EXPORT)
    adapter = ChatGPTAdapter()
    turns = adapter.parse_conversation(path)
    for i in range(len(turns) - 1):
        assert turns[i].turn_index < turns[i + 1].turn_index


def test_parse_conversation_no_tool_calls():
    path = _write_json(SAMPLE_EXPORT)
    adapter = ChatGPTAdapter()
    turns = adapter.parse_conversation(path)
    for turn in turns:
        assert turn.tool_calls == 0
        assert turn.tool_use_paths == []


def test_parse_conversation_empty_file():
    path = _write_json([])
    adapter = ChatGPTAdapter()
    turns = adapter.parse_conversation(path)
    assert turns == []


def test_parse_conversation_invalid_conv_id():
    path = _write_json(SAMPLE_EXPORT)
    adapter = ChatGPTAdapter()
    turns = adapter.parse_conversation(path, conv_id="nonexistent-id")
    assert turns == []

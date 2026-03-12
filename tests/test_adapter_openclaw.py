"""Tests for OpenClaw adapter."""

from __future__ import annotations

from reprompt.adapters.openclaw import OpenClawAdapter

# ---------------------------------------------------------------------------
# detect_installed — new path (primary)
# ---------------------------------------------------------------------------


def test_detect_installed_new_path(tmp_path):
    """New ~/.openclaw layout triggers detect_installed."""
    new_root = tmp_path / ".openclaw"
    new_root.mkdir(parents=True)
    adapter = OpenClawAdapter(session_path=new_root, legacy_path=tmp_path / "nonexistent")
    assert adapter.detect_installed()


def test_detect_installed_legacy_path(tmp_path):
    """Legacy ~/.opencode/sessions layout still triggers detect_installed."""
    legacy_root = tmp_path / ".opencode" / "sessions"
    legacy_root.mkdir(parents=True)
    adapter = OpenClawAdapter(session_path=tmp_path / "nonexistent", legacy_path=legacy_root)
    assert adapter.detect_installed()


def test_detect_installed_both_paths(tmp_path):
    """Both paths present — still detected as installed."""
    new_root = tmp_path / ".openclaw"
    new_root.mkdir(parents=True)
    legacy_root = tmp_path / ".opencode" / "sessions"
    legacy_root.mkdir(parents=True)
    adapter = OpenClawAdapter(session_path=new_root, legacy_path=legacy_root)
    assert adapter.detect_installed()


def test_detect_not_installed(tmp_path):
    """Neither path exists — not installed."""
    adapter = OpenClawAdapter(
        session_path=tmp_path / "nonexistent",
        legacy_path=tmp_path / "also_nonexistent",
    )
    assert not adapter.detect_installed()


# ---------------------------------------------------------------------------
# discover_sessions — dual-path traversal
# ---------------------------------------------------------------------------


def _write_jsonl(path: Path, name: str = "session.jsonl") -> Path:  # noqa: F821
    """Helper: create a minimal JSONL file at path/name."""
    path.mkdir(parents=True, exist_ok=True)
    f = path / name
    f.write_text('{"role":"user","content":"hello world test","session_id":"s1","timestamp":"t"}\n')
    return f


def test_discover_sessions_new_path_only(tmp_path):
    """Files under new path are discovered."""
    new_root = tmp_path / ".openclaw"
    _write_jsonl(new_root / "agents" / "agent1" / "sessions", "sess.jsonl")
    adapter = OpenClawAdapter(session_path=new_root, legacy_path=tmp_path / "nonexistent")
    sessions = adapter.discover_sessions()
    assert len(sessions) == 1
    assert sessions[0].name == "sess.jsonl"


def test_discover_sessions_legacy_path_only(tmp_path):
    """Files under legacy path are discovered."""
    legacy_root = tmp_path / ".opencode" / "sessions"
    _write_jsonl(legacy_root / "my-project", "sess.jsonl")
    adapter = OpenClawAdapter(session_path=tmp_path / "nonexistent", legacy_path=legacy_root)
    sessions = adapter.discover_sessions()
    assert len(sessions) == 1
    assert sessions[0].name == "sess.jsonl"


def test_discover_sessions_both_paths(tmp_path):
    """Files from both paths are combined without duplication."""
    new_root = tmp_path / ".openclaw"
    legacy_root = tmp_path / ".opencode" / "sessions"
    _write_jsonl(new_root / "agents" / "agent1" / "sessions", "new.jsonl")
    _write_jsonl(legacy_root / "my-project", "old.jsonl")
    adapter = OpenClawAdapter(session_path=new_root, legacy_path=legacy_root)
    sessions = adapter.discover_sessions()
    names = {s.name for s in sessions}
    assert names == {"new.jsonl", "old.jsonl"}


def test_discover_sessions_empty(tmp_path):
    """No sessions found when neither path exists."""
    adapter = OpenClawAdapter(
        session_path=tmp_path / "nonexistent",
        legacy_path=tmp_path / "also_nonexistent",
    )
    assert adapter.discover_sessions() == []


# ---------------------------------------------------------------------------
# parse_session
# ---------------------------------------------------------------------------


def test_parse_session(fixtures_path):
    adapter = OpenClawAdapter()
    prompts = adapter.parse_session(fixtures_path / "openclaw_session.jsonl")
    assert len(prompts) >= 3
    assert all(p.source == "openclaw" for p in prompts)


def test_filters_noise(fixtures_path):
    adapter = OpenClawAdapter()
    prompts = adapter.parse_session(fixtures_path / "openclaw_session.jsonl")
    texts = [p.text for p in prompts]
    # Short/noise messages should be filtered
    for t in texts:
        assert len(t) >= 10


def test_filters_assistant_messages(fixtures_path):
    adapter = OpenClawAdapter()
    prompts = adapter.parse_session(fixtures_path / "openclaw_session.jsonl")
    # No assistant messages
    for p in prompts:
        assert "I'll implement" not in p.text


def test_prompts_have_timestamps(fixtures_path):
    adapter = OpenClawAdapter()
    prompts = adapter.parse_session(fixtures_path / "openclaw_session.jsonl")
    assert all(p.timestamp for p in prompts)


def test_prompts_have_session_id(fixtures_path):
    adapter = OpenClawAdapter()
    prompts = adapter.parse_session(fixtures_path / "openclaw_session.jsonl")
    # Session ID from the JSONL data
    assert all(p.session_id == "sess_123" for p in prompts)


# ---------------------------------------------------------------------------
# _project_from_path — both path layouts
# ---------------------------------------------------------------------------


def test_extracts_project_legacy_path():
    """Legacy: ~/.opencode/sessions/<project>/sess.jsonl -> project name."""
    adapter = OpenClawAdapter()
    name = adapter._project_from_path("/Users/chris/.opencode/sessions/my-project/sess.jsonl")
    assert name == "my-project"


def test_extracts_project_new_path():
    """New: ~/.openclaw/agents/<agentId>/sessions/<project>/sess.jsonl -> project name."""
    adapter = OpenClawAdapter()
    name = adapter._project_from_path(
        "/Users/chris/.openclaw/agents/agent-abc/sessions/my-project/sess.jsonl"
    )
    assert name == "my-project"


def test_project_empty_when_parent_is_sessions():
    """Returns '' when file sits directly inside a 'sessions' directory."""
    adapter = OpenClawAdapter()
    name = adapter._project_from_path("/Users/chris/.openclaw/agents/agent-abc/sessions/sess.jsonl")
    assert name == ""


def test_project_empty_when_parent_is_agents():
    """Returns '' when file sits directly inside an 'agents' directory."""
    adapter = OpenClawAdapter()
    name = adapter._project_from_path("/Users/chris/.openclaw/agents/sess.jsonl")
    assert name == ""


# ---------------------------------------------------------------------------
# misc
# ---------------------------------------------------------------------------


def test_name_attribute():
    adapter = OpenClawAdapter()
    assert adapter.name == "openclaw"


def test_default_session_path_is_new_location():
    """default_session_path reflects the new ~/.openclaw primary location."""
    assert ".openclaw" in OpenClawAdapter.default_session_path


# ---------------------------------------------------------------------------
# parse_session_meta — metadata extraction
# ---------------------------------------------------------------------------
import json as _json  # noqa: E402
from pathlib import Path as _Path  # noqa: E402 (Path already in scope via fixtures)


def _write_meta_jsonl(path: _Path, entries: list[dict], name: str = "session.jsonl") -> _Path:
    """Helper: write a JSONL session file with given entries."""
    path.mkdir(parents=True, exist_ok=True)
    f = path / name
    f.write_text("\n".join(_json.dumps(e) for e in entries) + "\n")
    return f


def test_parse_session_meta_returns_session_meta(tmp_path):
    from reprompt.core.session_meta import SessionMeta

    session_dir = tmp_path / "proj"
    entries = [
        {
            "role": "user",
            "content": "Fix the failing tests for auth module",
            "session_id": "s1",
            "timestamp": "2026-03-10T10:00:00Z",
        },
        {
            "role": "assistant",
            "content": "I'll look at the tests now.",
            "session_id": "s1",
            "timestamp": "2026-03-10T10:01:00Z",
        },
        {
            "role": "user",
            "content": "Also update the README with the new API",
            "session_id": "s1",
            "timestamp": "2026-03-10T10:02:00Z",
        },
        {
            "role": "assistant",
            "content": "Done! All tests passing.",
            "session_id": "s1",
            "timestamp": "2026-03-10T10:05:00Z",
        },
    ]
    f = _write_meta_jsonl(session_dir, entries)
    adapter = OpenClawAdapter(session_path=tmp_path, legacy_path=tmp_path / "nonexistent")
    meta = adapter.parse_session_meta(f)
    assert isinstance(meta, SessionMeta)
    assert meta.source == "openclaw"
    assert meta.prompt_count == 2
    assert meta.session_id == "s1"


def test_parse_session_meta_duration_computed(tmp_path):
    session_dir = tmp_path / "proj"
    entries = [
        {
            "role": "user",
            "content": "Write unit tests for the parser",
            "session_id": "s2",
            "timestamp": "2026-03-10T10:00:00Z",
        },
        {
            "role": "assistant",
            "content": "OK.",
            "session_id": "s2",
            "timestamp": "2026-03-10T10:10:00Z",
        },
    ]
    f = _write_meta_jsonl(session_dir, entries)
    adapter = OpenClawAdapter(session_path=tmp_path, legacy_path=tmp_path / "nonexistent")
    meta = adapter.parse_session_meta(f)
    assert meta is not None
    assert meta.duration_seconds == 600


def test_parse_session_meta_error_detected(tmp_path):
    session_dir = tmp_path / "proj"
    entries = [
        {
            "role": "user",
            "content": "Fix the broken deployment pipeline",
            "session_id": "s3",
            "timestamp": "2026-03-10T10:00:00Z",
        },
        {
            "role": "assistant",
            "content": "Error: module 'foo' not found.",
            "session_id": "s3",
            "timestamp": "2026-03-10T10:01:00Z",
        },
        {
            "role": "assistant",
            "content": "Traceback (most recent call last): ...",
            "session_id": "s3",
            "timestamp": "2026-03-10T10:02:00Z",
        },
    ]
    f = _write_meta_jsonl(session_dir, entries)
    adapter = OpenClawAdapter(session_path=tmp_path, legacy_path=tmp_path / "nonexistent")
    meta = adapter.parse_session_meta(f)
    assert meta is not None
    assert meta.error_count == 2


def test_parse_session_meta_tool_calls_zero(tmp_path):
    session_dir = tmp_path / "proj"
    entries = [
        {
            "role": "user",
            "content": "Refactor the database connection handling",
            "session_id": "s4",
            "timestamp": "2026-03-10T10:00:00Z",
        },
        {
            "role": "assistant",
            "content": "Sure, I'll refactor it.",
            "session_id": "s4",
            "timestamp": "2026-03-10T10:01:00Z",
        },
    ]
    f = _write_meta_jsonl(session_dir, entries)
    adapter = OpenClawAdapter(session_path=tmp_path, legacy_path=tmp_path / "nonexistent")
    meta = adapter.parse_session_meta(f)
    assert meta is not None
    assert meta.tool_call_count == 0


def test_parse_session_meta_returns_none_no_user_prompts(tmp_path):
    session_dir = tmp_path / "proj"
    entries = [
        {
            "role": "assistant",
            "content": "Hello, I am ready to help.",
            "session_id": "s5",
            "timestamp": "2026-03-10T10:00:00Z",
        },
    ]
    f = _write_meta_jsonl(session_dir, entries)
    adapter = OpenClawAdapter(session_path=tmp_path, legacy_path=tmp_path / "nonexistent")
    meta = adapter.parse_session_meta(f)
    assert meta is None


def test_parse_session_meta_returns_none_empty_file(tmp_path):
    session_dir = tmp_path / "proj"
    session_dir.mkdir(parents=True, exist_ok=True)
    f = session_dir / "empty.jsonl"
    f.write_text("")
    adapter = OpenClawAdapter(session_path=tmp_path, legacy_path=tmp_path / "nonexistent")
    meta = adapter.parse_session_meta(f)
    assert meta is None


def test_parse_session_meta_avg_prompt_length(tmp_path):
    session_dir = tmp_path / "proj"
    p1 = "A" * 100
    p2 = "B" * 200
    entries = [
        {"role": "user", "content": p1, "session_id": "s6", "timestamp": "2026-03-10T10:00:00Z"},
        {"role": "user", "content": p2, "session_id": "s6", "timestamp": "2026-03-10T10:01:00Z"},
        {
            "role": "assistant",
            "content": "Done.",
            "session_id": "s6",
            "timestamp": "2026-03-10T10:02:00Z",
        },
    ]
    f = _write_meta_jsonl(session_dir, entries)
    adapter = OpenClawAdapter(session_path=tmp_path, legacy_path=tmp_path / "nonexistent")
    meta = adapter.parse_session_meta(f)
    assert meta is not None
    assert meta.avg_prompt_length == 150.0


def test_parse_session_meta_project_from_path(tmp_path):
    session_dir = tmp_path / "my-project"
    entries = [
        {
            "role": "user",
            "content": "Add pagination to the search results",
            "session_id": "s7",
            "timestamp": "2026-03-10T10:00:00Z",
        },
    ]
    f = _write_meta_jsonl(session_dir, entries)
    adapter = OpenClawAdapter(session_path=tmp_path, legacy_path=tmp_path / "nonexistent")
    meta = adapter.parse_session_meta(f)
    assert meta is not None
    assert meta.project == "my-project"

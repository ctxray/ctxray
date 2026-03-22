# tests/test_privacy.py
"""Tests for the privacy metadata registry and summary computation."""

from __future__ import annotations

from reprompt.core.privacy import (
    ADAPTER_PRIVACY,
    PrivacyProfile,
    compute_privacy_summary,
    get_profile,
)


class TestPrivacyProfile:
    """Test the PrivacyProfile dataclass."""

    def test_create_profile(self):
        p = PrivacyProfile(cloud=True, retention="persistent", training="never")
        assert p.cloud is True
        assert p.retention == "persistent"
        assert p.training == "never"
        assert p.note == ""

    def test_create_profile_with_note(self):
        p = PrivacyProfile(cloud=False, retention="none", training="never", note="All local")
        assert p.note == "All local"

    def test_frozen(self):
        p = PrivacyProfile(cloud=True, retention="transient", training="opt-out")
        try:
            p.cloud = False  # type: ignore[misc]
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass


class TestAdapterPrivacyRegistry:
    """Test the ADAPTER_PRIVACY registry has correct entries."""

    def test_has_all_eight_adapters(self):
        expected = {
            "claude-code",
            "cursor",
            "openclaw",
            "aider",
            "gemini",
            "cline",
            "chatgpt-export",
            "claude-chat-export",
        }
        assert set(ADAPTER_PRIVACY.keys()) == expected

    def test_claude_code_profile(self):
        p = ADAPTER_PRIVACY["claude-code"]
        assert p.cloud is True
        assert p.retention == "policy-dependent"
        assert p.training == "never"

    def test_cursor_profile(self):
        p = ADAPTER_PRIVACY["cursor"]
        assert p.cloud is True
        assert p.retention == "transient"
        assert p.training == "never"

    def test_openclaw_profile(self):
        p = ADAPTER_PRIVACY["openclaw"]
        assert p.cloud is True
        assert p.retention == "policy-dependent"
        assert p.training == "unknown"

    def test_aider_profile(self):
        p = ADAPTER_PRIVACY["aider"]
        assert p.cloud is False
        assert p.retention == "none"
        assert p.training == "never"

    def test_gemini_profile(self):
        p = ADAPTER_PRIVACY["gemini"]
        assert p.cloud is True
        assert p.retention == "transient"
        assert p.training == "opt-out"

    def test_cline_profile(self):
        p = ADAPTER_PRIVACY["cline"]
        assert p.cloud is True
        assert p.retention == "policy-dependent"
        assert p.training == "unknown"

    def test_chatgpt_export_profile(self):
        p = ADAPTER_PRIVACY["chatgpt-export"]
        assert p.cloud is True
        assert p.retention == "persistent"
        assert p.training == "opt-out"

    def test_claude_chat_export_profile(self):
        p = ADAPTER_PRIVACY["claude-chat-export"]
        assert p.cloud is True
        assert p.retention == "persistent"
        assert p.training == "never"

    def test_all_profiles_are_privacy_profile(self):
        for name, profile in ADAPTER_PRIVACY.items():
            assert isinstance(profile, PrivacyProfile), f"{name} is not a PrivacyProfile"


class TestGetProfile:
    """Test the get_profile lookup function."""

    def test_known_adapter(self):
        p = get_profile("claude-code")
        assert p.cloud is True
        assert p.training == "never"

    def test_another_known_adapter(self):
        p = get_profile("aider")
        assert p.cloud is False

    def test_unknown_adapter_returns_fallback(self):
        p = get_profile("nonexistent-tool")
        assert p.cloud is True
        assert p.retention == "unknown"
        assert p.training == "unknown"

    def test_empty_string_returns_fallback(self):
        p = get_profile("")
        assert p.retention == "unknown"
        assert p.training == "unknown"


class TestComputePrivacySummary:
    """Test the compute_privacy_summary function."""

    def test_empty_input(self):
        result = compute_privacy_summary({})
        assert result["total_prompts"] == 0
        assert result["cloud_prompts"] == 0
        assert result["local_prompts"] == 0
        assert result["training_exposed"] == 0
        assert result["training_safe"] == 0
        assert result["sources"] == []

    def test_single_local_source(self):
        result = compute_privacy_summary({"aider": 10})
        assert result["total_prompts"] == 10
        assert result["cloud_prompts"] == 0
        assert result["local_prompts"] == 10
        assert result["training_exposed"] == 0
        assert result["training_safe"] == 10

    def test_single_cloud_source(self):
        result = compute_privacy_summary({"chatgpt-export": 5})
        assert result["total_prompts"] == 5
        assert result["cloud_prompts"] == 5
        assert result["local_prompts"] == 0
        # chatgpt-export has training="opt-out" => exposed
        assert result["training_exposed"] == 5
        assert result["training_safe"] == 0

    def test_mixed_sources(self):
        counts = {"claude-code": 20, "aider": 10, "chatgpt-export": 5}
        result = compute_privacy_summary(counts)
        assert result["total_prompts"] == 35
        assert result["cloud_prompts"] == 25  # claude-code + chatgpt-export
        assert result["local_prompts"] == 10  # aider
        # claude-code training="never" => safe (20)
        # aider training="never" => safe (10)
        # chatgpt-export training="opt-out" => exposed (5)
        assert result["training_safe"] == 30
        assert result["training_exposed"] == 5

    def test_sources_sorted_by_count_descending(self):
        counts = {"aider": 3, "claude-code": 10, "gemini": 7}
        result = compute_privacy_summary(counts)
        sources = result["sources"]
        assert len(sources) == 3
        assert sources[0]["source"] == "claude-code"
        assert sources[0]["count"] == 10
        assert sources[1]["source"] == "gemini"
        assert sources[1]["count"] == 7
        assert sources[2]["source"] == "aider"
        assert sources[2]["count"] == 3

    def test_source_detail_fields(self):
        result = compute_privacy_summary({"claude-code": 15})
        sources = result["sources"]
        assert len(sources) == 1
        detail = sources[0]
        assert detail["source"] == "claude-code"
        assert detail["count"] == 15
        assert detail["cloud"] is True
        assert detail["retention"] == "policy-dependent"
        assert detail["training"] == "never"

    def test_unknown_source_uses_fallback(self):
        result = compute_privacy_summary({"some-unknown-tool": 8})
        assert result["total_prompts"] == 8
        assert result["cloud_prompts"] == 8  # fallback is cloud=True
        # fallback training="unknown" => exposed
        assert result["training_exposed"] == 8
        sources = result["sources"]
        assert sources[0]["training"] == "unknown"

    def test_training_categories(self):
        # "never" => safe, "opt-out" => exposed, "opt-in" => exposed, "unknown" => exposed
        counts = {
            "claude-code": 10,  # training="never" => safe
            "gemini": 5,  # training="opt-out" => exposed
            "openclaw": 3,  # training="unknown" => exposed
        }
        result = compute_privacy_summary(counts)
        assert result["training_safe"] == 10
        assert result["training_exposed"] == 8  # 5 + 3

    def test_all_safe_training(self):
        counts = {"claude-code": 10, "aider": 5, "cursor": 3}
        result = compute_privacy_summary(counts)
        assert result["training_safe"] == 18
        assert result["training_exposed"] == 0


class TestPrivacyInReportData:
    def test_report_data_includes_privacy(self, tmp_path, monkeypatch):
        """build_report_data should include a 'privacy' key."""
        from reprompt.config import Settings
        from reprompt.core.pipeline import build_report_data
        from reprompt.storage.db import PromptDB

        db_path = tmp_path / "test.db"
        monkeypatch.setenv("REPROMPT_DB_PATH", str(db_path))
        settings = Settings()
        db = PromptDB(db_path)

        # Insert prompts from different sources
        db.insert_prompt("fix the bug", source="claude-code", project="proj", session_id="s1")
        db.insert_prompt("add feature", source="aider", project="proj", session_id="s2")

        data = build_report_data(settings=settings)
        assert "privacy" in data
        assert data["privacy"]["total_prompts"] == 2
        assert data["privacy"]["cloud_prompts"] == 1  # claude-code
        assert data["privacy"]["local_prompts"] == 1  # aider

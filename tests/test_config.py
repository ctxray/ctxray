"""Tests for ctxray configuration module."""

from ctxray.config import Settings


def test_default_settings():
    s = Settings()
    assert s.embedding_backend == "tfidf"
    assert s.dedup_threshold == 0.85
    assert s.library_min_frequency == 3
    assert "ctxray" in str(s.db_path).lower()


def test_env_override(monkeypatch):
    monkeypatch.setenv("CTXRAY_EMBEDDING_BACKEND", "ollama")
    s = Settings()
    assert s.embedding_backend == "ollama"


def test_db_path_expanduser():
    s = Settings()
    assert "~" not in str(s.db_path)


# --- TOML config loading tests ---


def test_toml_config_loaded(tmp_path, monkeypatch):
    """TOML file values are loaded when the file exists."""
    config_dir = tmp_path / ".config" / "ctxray"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.toml"
    config_file.write_text(
        "[ctxray]\n"
        'embedding_backend = "ollama"\n'
        "dedup_threshold = 0.75\n"
        'ollama_url = "http://myhost:11434"\n'
    )
    monkeypatch.setenv("CTXRAY_CONFIG_PATH", str(config_file))
    # Clear any env overrides that might interfere
    monkeypatch.delenv("CTXRAY_EMBEDDING_BACKEND", raising=False)
    monkeypatch.delenv("CTXRAY_DEDUP_THRESHOLD", raising=False)
    monkeypatch.delenv("CTXRAY_OLLAMA_URL", raising=False)

    s = Settings()
    assert s.embedding_backend == "ollama"
    assert s.dedup_threshold == 0.75
    assert s.ollama_url == "http://myhost:11434"


def test_env_overrides_toml(tmp_path, monkeypatch):
    """Env vars take precedence over TOML values."""
    config_dir = tmp_path / ".config" / "ctxray"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.toml"
    config_file.write_text('[ctxray]\nembedding_backend = "ollama"\ndedup_threshold = 0.75\n')
    monkeypatch.setenv("CTXRAY_CONFIG_PATH", str(config_file))
    # Env var should override TOML
    monkeypatch.setenv("CTXRAY_EMBEDDING_BACKEND", "tfidf")
    monkeypatch.delenv("CTXRAY_DEDUP_THRESHOLD", raising=False)

    s = Settings()
    assert s.embedding_backend == "tfidf"  # env wins
    assert s.dedup_threshold == 0.75  # TOML value (no env override)


def test_toml_missing_file_uses_defaults(tmp_path, monkeypatch):
    """When TOML file does not exist, defaults are used."""
    monkeypatch.setenv("CTXRAY_CONFIG_PATH", str(tmp_path / "nonexistent.toml"))
    monkeypatch.delenv("CTXRAY_EMBEDDING_BACKEND", raising=False)
    monkeypatch.delenv("CTXRAY_DEDUP_THRESHOLD", raising=False)

    s = Settings()
    assert s.embedding_backend == "tfidf"
    assert s.dedup_threshold == 0.85


def test_toml_empty_section_uses_defaults(tmp_path, monkeypatch):
    """TOML file exists but has no [ctxray] section."""
    config_dir = tmp_path / ".config" / "ctxray"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.toml"
    config_file.write_text("[other]\nfoo = 1\n")
    monkeypatch.setenv("CTXRAY_CONFIG_PATH", str(config_file))
    monkeypatch.delenv("CTXRAY_EMBEDDING_BACKEND", raising=False)

    s = Settings()
    assert s.embedding_backend == "tfidf"

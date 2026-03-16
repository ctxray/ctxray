"""Configuration with env var override and TOML file support.

Priority order (highest wins): init kwargs > env vars > TOML file > field defaults.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10
        import tomli as tomllib  # type: ignore[no-redefine]


def _default_db_path() -> str:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", "~"))
    elif hasattr(os, "uname") and os.uname().sysname == "Darwin":
        base = Path("~/Library/Application Support")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share"))
    return str(base / "reprompt" / "reprompt.db")


def _default_config_path() -> Path:
    """Return default TOML config path, respecting XDG on Linux."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", "~"))
    elif hasattr(os, "uname") and os.uname().sysname == "Darwin":
        base = Path("~/.config")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config"))
    return base.expanduser() / "reprompt" / "config.toml"


def _load_toml_config() -> dict[str, Any]:
    """Load TOML config file. Returns empty dict if file missing or invalid."""
    config_path_str = os.environ.get("REPROMPT_CONFIG_PATH")
    if config_path_str:
        config_path = Path(config_path_str)
    else:
        config_path = _default_config_path()

    if not config_path.is_file():
        return {}

    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        return dict(data.get("reprompt", {}))
    except Exception:
        return {}


class _TomlConfigSource(PydanticBaseSettingsSource):
    """Custom settings source that loads from a TOML config file."""

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        toml_data = _load_toml_config()
        if field_name in toml_data:
            return toml_data[field_name], field_name, False
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return _load_toml_config()


class Settings(BaseSettings):
    model_config = {"env_prefix": "REPROMPT_", "extra": "ignore"}

    # Embedding
    embedding_backend: str = "tfidf"
    ollama_url: str = "http://localhost:11434"

    # Storage
    db_path: Path = Path(os.path.expanduser(_default_db_path()))

    # Dedup
    dedup_threshold: float = 0.85

    # Library
    library_min_frequency: int = 3
    library_categories: list[str] = [
        "debug",
        "implement",
        "review",
        "test",
        "refactor",
        "explain",
        "config",
    ]

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Insert TOML source between env vars and defaults.

        Priority: init_settings > env_settings > toml_file > defaults
        """
        return (
            init_settings,
            env_settings,
            _TomlConfigSource(settings_cls),
        )

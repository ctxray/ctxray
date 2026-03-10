"""Core data models."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class Prompt:
    """A single prompt extracted from an AI coding session."""

    text: str
    source: str
    session_id: str
    project: str | None = None
    timestamp: str = ""
    char_count: int = field(init=False)
    hash: str = field(init=False)

    def __post_init__(self) -> None:
        stripped = self.text.strip()
        self.char_count = len(stripped)
        self.hash = hashlib.sha256(stripped.encode()).hexdigest()

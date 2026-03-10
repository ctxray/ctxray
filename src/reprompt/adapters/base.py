"""Base adapter interface for AI coding session parsers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from reprompt.core.models import Prompt


class BaseAdapter(ABC):
    """Abstract base class for session adapters."""

    name: str
    default_session_path: str

    @abstractmethod
    def parse_session(self, path: Path) -> list[Prompt]:
        """Parse a session file and return a list of Prompt objects."""
        ...

    @abstractmethod
    def detect_installed(self) -> bool:
        """Check if the tool's session directory exists."""
        ...

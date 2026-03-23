"""Base adapter interface for AI coding session parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from reprompt.core.conversation import ConversationTurn
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

    def parse_conversation(self, path: Path) -> list[ConversationTurn]:
        """Parse full conversation with both roles.

        Default implementation wraps parse_session() results as user-only turns.
        Override in adapters that can extract assistant turns.
        """
        prompts = self.parse_session(path)
        return [
            ConversationTurn(
                role="user",
                text=p.text,
                timestamp=p.timestamp,
                turn_index=i,
            )
            for i, p in enumerate(prompts)
        ]

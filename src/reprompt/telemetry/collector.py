"""Telemetry collector -- orchestrates consent check, event creation, queueing, and sending.

Usage in CLI commands:
    collector = get_collector()
    collector.record(dna, scores)   # enqueue if opted-in
    collector.flush()               # attempt to send batch (fire-and-forget)
"""

from __future__ import annotations

import logging
from pathlib import Path

from reprompt.core.prompt_dna import PromptDNA
from reprompt.core.scorer import ScoreBreakdown
from reprompt.telemetry.consent import (
    TelemetryConsent,
    generate_install_id,
    get_or_create_salt,
    read_consent,
)
from reprompt.telemetry.events import build_event
from reprompt.telemetry.queue import TelemetryQueue
from reprompt.telemetry.sender import send_batch

logger = logging.getLogger(__name__)


class TelemetryCollector:
    """Coordinates telemetry event lifecycle.

    1. Check consent (only OPTED_IN triggers telemetry)
    2. Build anonymous event from PromptDNA + scores
    3. Enqueue locally (SQLite)
    4. Flush: send batch to server, acknowledge on success
    """

    def __init__(
        self,
        *,
        config_path: Path,
        queue_path: Path,
        version: str,
    ) -> None:
        self.config_path = config_path
        self.version = version
        self.queue = TelemetryQueue(queue_path)

        # Lazily computed install_id (cached)
        self._install_id: str | None = None

    @property
    def consent(self) -> TelemetryConsent:
        """Read current consent from config file."""
        return read_consent(self.config_path)

    @property
    def install_id(self) -> str:
        """Get or create the stable install_id."""
        if self._install_id is None:
            salt = get_or_create_salt(self.config_path)
            self._install_id = generate_install_id(salt)
        return self._install_id

    def record(
        self,
        dna: PromptDNA,
        scores: ScoreBreakdown,
        *,
        session_duration_seconds: int | None = None,
        error_count: int | None = None,
        prompt_count: int | None = None,
        tool_call_count: int | None = None,
        effectiveness_score: float | None = None,
    ) -> None:
        """Record a telemetry event if user has opted in.

        Does nothing if consent is NOT_ASKED or OPTED_OUT.
        """
        if self.consent != TelemetryConsent.OPTED_IN:
            return

        event = build_event(
            install_id=self.install_id,
            dna=dna,
            scores=scores,
            version=self.version,
            session_duration_seconds=session_duration_seconds,
            error_count=error_count,
            prompt_count=prompt_count,
            tool_call_count=tool_call_count,
            effectiveness_score=effectiveness_score,
        )
        self.queue.enqueue(event.model_dump_json())

    def flush(self, *, batch_size: int = 50) -> None:
        """Attempt to send queued events to the server.

        Fire-and-forget: failures leave events in queue for next attempt.
        Also cleans up events older than 30 days.
        """
        if self.consent != TelemetryConsent.OPTED_IN:
            return

        # Clean up old events first
        self.queue.flush_old(max_age_days=30)

        # Dequeue a batch
        batch = self.queue.dequeue(limit=batch_size)
        if not batch:
            return

        ids = [row[0] for row in batch]
        payloads = [row[1] for row in batch]

        success = send_batch(payloads)
        if success:
            self.queue.acknowledge(ids)
            logger.debug("Telemetry: sent %d events", len(ids))
        else:
            logger.debug("Telemetry: send failed, %d events will retry", len(ids))


def get_collector() -> TelemetryCollector:
    """Create a TelemetryCollector using default config paths.

    Uses the same config path as Settings and stores the queue DB
    next to the main reprompt DB.
    """
    from reprompt.config import Settings, _default_config_path

    settings = Settings()
    config_path = _default_config_path()
    queue_path = settings.db_path.parent / "telemetry_queue.db"

    return TelemetryCollector(
        config_path=config_path,
        queue_path=queue_path,
        version=_get_version(),
    )


def _get_version() -> str:
    """Get the current reprompt version."""
    try:
        from importlib.metadata import version

        return version("reprompt-cli")
    except Exception:
        return "unknown"

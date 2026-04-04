"""HTTP batch sender for telemetry events.

Uses stdlib urllib.request (no extra dependencies). Fire-and-forget:
- 2-second timeout
- No retries on failure
- Events stay in queue if send fails
"""

from __future__ import annotations

import json
import logging
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "https://t.getreprompt.dev/v1/events"


def send_batch(
    event_payloads: list[str],
    *,
    endpoint: str = DEFAULT_ENDPOINT,
) -> bool:
    """Send a batch of telemetry event JSON strings to the server.

    Parameters
    ----------
    event_payloads:
        List of JSON strings, each a serialized TelemetryEvent.
    endpoint:
        The HTTP endpoint to POST to.

    Returns
    -------
    bool
        True if send succeeded (or batch was empty), False on any error.
    """
    if not event_payloads:
        return True

    body = json.dumps(
        {
            "events": [json.loads(p) for p in event_payloads],
        }
    ).encode("utf-8")

    request = Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=2) as response:
            return bool(response.status == 200)
    except Exception:
        # Fire-and-forget: log but don't raise
        logger.debug("Telemetry send failed (will retry next run)", exc_info=True)
        return False

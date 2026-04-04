"""HTTP client for the share API -- HMAC-SHA256 signed uploads."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

SHARE_ENDPOINT = "https://getreprompt.dev/api/share"


def sign_request(install_id: str, body: str) -> str:
    """Compute HMAC-SHA256(install_id, body) -> hex digest."""
    return hmac.new(install_id.encode(), body.encode(), hashlib.sha256).hexdigest()


def upload_share(
    *,
    install_id: str,
    report_json: str,
    endpoint: str = SHARE_ENDPOINT,
) -> str:
    """Upload a WrappedReport to the share API. Returns the share URL."""
    signature = sign_request(install_id, report_json)

    request = Request(
        endpoint,
        data=report_json.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Reprompt-Install": install_id,
            "X-Reprompt-Signature": signature,
            "User-Agent": "ctxray/1.0",
        },
        method="PUT",
    )

    try:
        with urlopen(request, timeout=5) as response:
            data = json.loads(response.read())
            return data["url"]
    except HTTPError as e:
        if e.code == 401:
            raise RuntimeError(
                "Share auth failed -- ensure you have telemetry enabled "
                "(`ctxray telemetry on`) and have scanned at least once."
            ) from e
        if e.code == 503:
            raise RuntimeError("Share service temporarily unavailable. Try again later.") from e
        raise RuntimeError(f"Share upload failed (HTTP {e.code})") from e
    except (URLError, ConnectionError, OSError) as e:
        raise RuntimeError(f"Share upload network error: {e}") from e

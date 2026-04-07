"""HTTP client for the share API -- HMAC-SHA256 signed uploads.

Share is opt-in. ctxray does not host a share service. Users must configure
their own endpoint via CTXRAY_SHARE_ENDPOINT env var or config.toml.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


def sign_request(install_id: str, body: str) -> str:
    """Compute HMAC-SHA256(install_id, body) -> hex digest."""
    return hmac.new(install_id.encode(), body.encode(), hashlib.sha256).hexdigest()


def upload_share(
    *,
    install_id: str,
    report_json: str,
    endpoint: str,
) -> str:
    """Upload a WrappedReport to the share API. Returns the share URL.

    Requires an explicit endpoint — ctxray does not host a share service.
    """
    if not endpoint:
        raise RuntimeError(
            "Share endpoint not configured. ctxray does not host a share service.\n"
            "Set CTXRAY_SHARE_ENDPOINT=https://your-endpoint.example/share\n"
            'Or in ~/.config/ctxray/config.toml: share_endpoint = "https://..."'
        )
    signature = sign_request(install_id, report_json)

    request = Request(
        endpoint,
        data=report_json.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Ctxray-Install": install_id,
            "X-Ctxray-Signature": signature,
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

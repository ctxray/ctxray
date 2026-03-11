"""JSON output format."""

from __future__ import annotations

import json
from typing import Any


def format_json_report(data: dict[str, Any]) -> str:
    """Format report data as JSON string."""
    return json.dumps(data, indent=2, default=str)

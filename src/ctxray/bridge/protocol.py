"""Chrome/Firefox Native Messaging stdio protocol.

Wire format: 4-byte unsigned int (native byte order) + UTF-8 JSON payload.
Ref: https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging
"""

from __future__ import annotations

import json
import struct
from typing import IO, Any

# 4-byte native-endian unsigned int
_HEADER_FMT = "@I"
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)

# Chrome Native Messaging protocol limit: 1 MB
_MAX_MESSAGE_SIZE = 1 * 1024 * 1024


def read_message(stream: IO[bytes]) -> dict[str, Any] | None:
    """Read one length-prefixed JSON message from a binary stream.

    Returns None on EOF or incomplete header (signals shutdown).
    Raises ValueError if message exceeds 1 MB Chrome NM limit.
    """
    header = stream.read(_HEADER_SIZE)
    if len(header) < _HEADER_SIZE:
        return None
    (length,) = struct.unpack(_HEADER_FMT, header)
    if length > _MAX_MESSAGE_SIZE:
        raise ValueError(f"Message size {length} exceeds 1 MB limit")
    payload = stream.read(length)
    if len(payload) < length:
        return None
    try:
        return json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Invalid JSON payload: {exc}") from exc


def write_message(stream: IO[bytes], message: dict[str, Any]) -> None:
    """Write one length-prefixed JSON message to a binary stream."""
    payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
    stream.write(struct.pack(_HEADER_FMT, len(payload)))
    stream.write(payload)
    stream.flush()

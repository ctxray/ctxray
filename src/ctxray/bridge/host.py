"""Native Messaging host entry point.

Chrome/Firefox launches this as a subprocess. It reads messages from stdin,
processes them via the handler, and writes responses to stdout.

Usage (via shell wrapper):
    python -u -m ctxray.bridge.host

The -u flag ensures unbuffered stdin/stdout, critical for the binary protocol.
"""

from __future__ import annotations

import sys

from ctxray.bridge.handler import handle_message
from ctxray.bridge.protocol import read_message, write_message
from ctxray.config import Settings
from ctxray.storage.db import PromptDB


def run_host() -> None:
    """Main message loop. Runs until stdin closes."""
    settings = Settings()
    db = PromptDB(settings.db_path)

    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer

    while True:
        message = read_message(stdin)
        if message is None:
            break  # EOF — browser closed the connection
        response = handle_message(message, db)
        write_message(stdout, response)


if __name__ == "__main__":
    run_host()

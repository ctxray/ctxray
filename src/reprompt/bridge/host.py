"""Native Messaging host entry point.

Chrome/Firefox launches this as a subprocess. It reads messages from stdin,
processes them via the handler, and writes responses to stdout.

Usage (via shell wrapper):
    python -u -m reprompt.bridge.host

The -u flag ensures unbuffered stdin/stdout, critical for the binary protocol.
"""

from __future__ import annotations

import sys

from reprompt.bridge.handler import handle_message
from reprompt.bridge.protocol import read_message, write_message
from reprompt.config import Settings
from reprompt.storage.db import PromptDB


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

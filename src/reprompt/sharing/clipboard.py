"""Cross-platform clipboard copy. Best-effort, never raises."""

from __future__ import annotations

import subprocess
import sys


def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard. Returns True on success, False on failure."""
    try:
        if sys.platform == "darwin":
            cmd = ["pbcopy"]
        elif sys.platform.startswith("linux"):
            cmd = ["xclip", "-selection", "clipboard"]
        elif sys.platform == "win32":
            cmd = ["clip"]
        else:
            return False

        subprocess.run(cmd, input=text.encode(), check=True, timeout=3)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False

"""First-run telemetry consent prompt.

Shows a Rich-formatted prompt explaining what telemetry collects,
then writes the user's choice to the TOML config.
"""

from __future__ import annotations

from pathlib import Path

from reprompt.telemetry.consent import TelemetryConsent, read_consent, write_consent


def maybe_prompt_consent(config_path: Path, *, interactive: bool = True) -> bool:
    """Prompt for telemetry consent if not already decided.

    Parameters
    ----------
    config_path:
        Path to the TOML config file.
    interactive:
        If False, skip the prompt (CI/pipe environments).

    Returns
    -------
    bool
        True if a prompt was shown (consent was NOT_ASKED and is now decided).
        False if consent was already decided or not interactive.
    """
    current = read_consent(config_path)
    if current != TelemetryConsent.NOT_ASKED:
        return False

    if not interactive:
        return False

    accepted = _ask_consent_rich()
    if accepted:
        write_consent(TelemetryConsent.OPTED_IN, config_path)
    else:
        write_consent(TelemetryConsent.OPTED_OUT, config_path)
    return True


def _ask_consent_rich() -> bool:
    """Show a Rich-formatted consent prompt. Returns True if user accepts."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console(stderr=True)  # Use stderr so it doesn't mix with JSON output

    console.print()
    console.print(
        Panel(
            "[bold]Help improve reprompt?[/bold]\n\n"
            "reprompt can send [bold]anonymous[/bold] usage data to help improve "
            "scoring models.\n\n"
            "[bold]What is sent:[/bold]\n"
            "  \u2022 DNA feature vectors (numeric scores, not text)\n"
            "  \u2022 Score breakdown and task type\n"
            "  \u2022 Bucketed session outcomes\n\n"
            "[bold]What is never sent:[/bold]\n"
            "  \u2022 No prompt text, no file paths, no project names\n"
            "  \u2022 No exact timestamps\n"
            "  \u2022 Install ID is a one-way hash\n\n"
            "Change anytime: [bold]reprompt telemetry on/off[/bold]",
            title="Telemetry",
            width=60,
        )
    )

    try:
        response = console.input("  Enable anonymous telemetry? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False

    return response in ("y", "yes")

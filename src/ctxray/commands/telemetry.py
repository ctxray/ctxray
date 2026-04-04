"""CLI telemetry commands -- on/off/status for anonymous telemetry."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console

telemetry_app = typer.Typer(help="Manage anonymous telemetry (opt-in only).")
console = Console()


def _telemetry_config_path() -> Path:
    """Resolve the telemetry config path from env or default."""
    env_path = os.environ.get("CTXRAY_CONFIG_PATH")
    if env_path:
        return Path(env_path)

    from ctxray.config import _default_config_path

    return _default_config_path()


@telemetry_app.command("on")
def telemetry_on() -> None:
    """Enable anonymous telemetry (DNA feature vectors only, no prompt text)."""
    from ctxray.telemetry.consent import TelemetryConsent, write_consent

    config_path = _telemetry_config_path()
    write_consent(TelemetryConsent.OPTED_IN, config_path)
    console.print("[green]Telemetry enabled.[/green] Opted in to anonymous data collection.")
    console.print("[dim]Only DNA feature vectors are sent. No prompt text, no file paths.[/dim]")


@telemetry_app.command("off")
def telemetry_off() -> None:
    """Disable anonymous telemetry."""
    from ctxray.telemetry.consent import TelemetryConsent, write_consent

    config_path = _telemetry_config_path()
    write_consent(TelemetryConsent.OPTED_OUT, config_path)
    console.print("[yellow]Telemetry disabled.[/yellow] Opted out of data collection.")


@telemetry_app.command("status")
def telemetry_status() -> None:
    """Show current telemetry consent status and privacy information."""
    from ctxray.telemetry.consent import TelemetryConsent, read_consent

    config_path = _telemetry_config_path()
    consent = read_consent(config_path)

    if consent == TelemetryConsent.OPTED_IN:
        console.print("[green]Status: Enabled[/green] (opted in)")
    elif consent == TelemetryConsent.OPTED_OUT:
        console.print("[yellow]Status: Disabled[/yellow] (opted out)")
    else:
        console.print("[dim]Status: Not configured[/dim] (telemetry not active)")

    console.print()
    console.print("[bold]What is collected:[/bold]")
    console.print("  - DNA feature vectors (numeric scores from regex analysis)")
    console.print("  - Score breakdown (structure, context, position, repetition, clarity)")
    console.print("  - Task type (debug, implement, etc.) and source (claude-code, etc.)")
    console.print("  - Bucketed session outcomes (duration range, error range)")
    console.print()
    console.print("[bold]What is never collected:[/bold]")
    console.print("  - No prompt text, no file paths, no project names")
    console.print("  - No exact timestamps (day-level only)")
    console.print("  - Install ID is a one-way hash, not reversible to your identity")
    console.print()
    console.print("Manage: [bold]ctxray telemetry on[/bold] / [bold]ctxray telemetry off[/bold]")

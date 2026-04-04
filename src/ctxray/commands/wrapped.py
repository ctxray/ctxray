"""CLI wrapped command -- generates Prompt DNA Reports."""

from __future__ import annotations

import json as json_mod
from pathlib import Path

import typer
from rich.console import Console

from ctxray.sharing.client import upload_share
from ctxray.sharing.clipboard import copy_to_clipboard

console = Console()


def _get_install_id(config_path: Path) -> str:
    """Get the install_id for HMAC signing."""
    from ctxray.telemetry.consent import generate_install_id, get_or_create_salt

    salt = get_or_create_salt(config_path)
    return generate_install_id(salt)


def wrapped(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    html: str | None = typer.Option(None, "--html", help="Save HTML card to file"),
    share: bool = typer.Option(False, "--share", help="Upload and get a shareable link"),
) -> None:
    """Generate your Prompt DNA Report -- persona, scores, and shareable card."""
    from ctxray.config import Settings
    from ctxray.core.wrapped import build_wrapped
    from ctxray.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    report = build_wrapped(db)

    if share:
        try:
            from ctxray.config import _default_config_path

            install_id = _get_install_id(_default_config_path())
            share_payload = report.to_dict()
            share_payload.pop("task_distribution", None)
            report_json = json_mod.dumps(share_payload)

            url = upload_share(install_id=install_id, report_json=report_json)
            console.print(f"\n[bold green]Share link:[/bold green] {url}")

            if copy_to_clipboard(url):
                console.print("[dim]Copied to clipboard[/dim]")
            else:
                console.print("[dim]Copy the link above to share[/dim]")
        except RuntimeError as e:
            console.print(f"\n[red]Share error:[/red] {e}")
        return

    if json_output:
        typer.echo(json_mod.dumps(report.to_dict(), indent=2))
    elif html:
        from ctxray.output.wrapped_html import render_wrapped_html

        html_content = render_wrapped_html(report)
        Path(html).write_text(html_content)
        console.print(f"[green]Saved HTML card to {html}[/green]")
    else:
        from ctxray.output.wrapped_terminal import render_wrapped

        typer.echo(render_wrapped(report))

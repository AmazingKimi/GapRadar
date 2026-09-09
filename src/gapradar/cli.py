from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .config import load_sources
from .detector import scan_source
from .store import load_events, merge_events, save_events

app = typer.Typer(no_args_is_help=True, help="Evidence-first market change radar.")
console = Console()


@app.command()
def scan(
    sources: Path = typer.Option(Path("config/sources.yml"), exists=True, readable=True),
    output: Path = typer.Option(Path("data/events.json")),
) -> None:
    """Scan configured first-party feeds and persist verified market-change events."""
    incoming = []
    failures = 0
    for source in load_sources(sources):
        try:
            found = scan_source(source)
            incoming.extend(found)
            console.print(f"[green]✓[/green] {source.vendor}/{source.name}: {len(found)} event(s)")
        except Exception as exc:  # one broken source must not kill the whole radar
            failures += 1
            console.print(f"[yellow]![/yellow] {source.vendor}/{source.name}: {exc}")

    merged = merge_events(load_events(output), incoming)
    save_events(output, merged)
    console.print(f"\nSaved {len(merged)} total event(s) to {output}. Source failures: {failures}.")


@app.command()
def report(
    events: Path = typer.Option(Path("data/events.json"), exists=True, readable=True),
) -> None:
    """Render a compact, evidence-aware event report."""
    rows = load_events(events)
    table = Table(title="GapRadar — Verified Market Changes")
    table.add_column("Type")
    table.add_column("Vendor / Product")
    table.add_column("Confidence")
    table.add_column("Headline")
    table.add_column("Official evidence")
    for event in rows:
        table.add_row(
            event.event_type.value,
            f"{event.vendor} / {event.product}",
            event.confidence.value,
            event.headline,
            str(len(event.official_evidence)),
        )
    console.print(table)


if __name__ == "__main__":
    app()

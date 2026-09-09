from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .config import load_sources
from .detector import probe_source, scan_source
from .render import render_dashboard
from .store import load_events, merge_events, save_events

app = typer.Typer(no_args_is_help=True, help="Evidence-first market change radar.")
console = Console()


@app.command()
def scan(
    sources: Path = typer.Option(Path("config/sources.yml"), exists=True, readable=True),
    output: Path = typer.Option(Path("data/events.json")),
) -> None:
    """Scan first-party feeds and persist verified market-change events."""
    incoming = []
    failures = 0
    configured = load_sources(sources)
    for source in configured:
        try:
            found = scan_source(source)
            incoming.extend(found)
            console.print(
                f"[green]✓[/green] {source.vendor}/{source.name}: "
                f"{len(found)} verified event(s), lookback={source.lookback_days}d"
            )
        except Exception as exc:  # one broken source must not kill the radar
            failures += 1
            console.print(f"[yellow]![/yellow] {source.vendor}/{source.name}: {exc}")

    merged = merge_events(load_events(output), incoming)
    save_events(output, merged)
    console.print(
        f"\nSources: {len(configured)} · new matches: {len(incoming)} · "
        f"stored: {len(merged)} · failures: {failures}"
    )


@app.command()
def doctor(
    sources: Path = typer.Option(Path("config/sources.yml"), exists=True, readable=True),
    output: Path = typer.Option(Path("data/source-health.json")),
    strict: bool = typer.Option(False, help="Exit non-zero if any source is unhealthy."),
) -> None:
    """Check official feed reachability and persist a machine-readable health snapshot."""
    table = Table(title="GapRadar — Source Health")
    table.add_column("Source")
    table.add_column("HTTP")
    table.add_column("Entries", justify="right")
    table.add_column("Official links", justify="right")
    table.add_column("Status")
    failures = 0
    rows: list[dict[str, object]] = []
    checked_at = datetime.now(timezone.utc).isoformat()

    for source in load_sources(sources):
        row: dict[str, object] = {
            "vendor": source.vendor,
            "name": source.name,
            "url": source.url,
            "checked_at": checked_at,
        }
        try:
            result = probe_source(source)
            healthy = result.entry_count > 0 and result.official_link_count > 0
            if not healthy:
                failures += 1
            row.update(
                status="ok" if healthy else "bad_feed",
                http_status=result.http_status,
                entry_count=result.entry_count,
                official_link_count=result.official_link_count,
                error=None,
            )
            table.add_row(
                f"{source.vendor}/{source.name}",
                str(result.http_status),
                str(result.entry_count),
                str(result.official_link_count),
                "OK" if healthy else "BAD FEED",
            )
        except Exception as exc:
            failures += 1
            row.update(
                status="error",
                http_status=None,
                entry_count=0,
                official_link_count=0,
                error=f"{type(exc).__name__}: {exc}",
            )
            table.add_row(f"{source.vendor}/{source.name}", "—", "0", "0", f"ERROR: {exc}")
        rows.append(row)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    console.print(table)
    console.print(f"Health snapshot written to {output}. Failures: {failures}.")
    if strict and failures:
        raise typer.Exit(code=2)


@app.command()
def report(
    events: Path = typer.Option(Path("data/events.json"), exists=True, readable=True),
) -> None:
    """Render a compact evidence-aware event report."""
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


@app.command("export")
def export_dashboard(
    events: Path = typer.Option(Path("data/events.json")),
    output: Path = typer.Option(Path("docs/index.html")),
) -> None:
    """Export a standalone HTML radar dashboard."""
    rows = load_events(events)
    render_dashboard(rows, output)
    console.print(f"Dashboard exported to {output} with {len(rows)} event(s).")


if __name__ == "__main__":
    app()

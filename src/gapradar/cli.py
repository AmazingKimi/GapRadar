from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .backtest import run_backtest
from .blindbacktest import run as run_blind_backtest
from .config import load_sources
from .detector import probe_source, scan_source
from .dossier import export_dossiers
from .reaction import validate_reactions
from .render import render_dashboard
from .store import load_events, merge_events, save_events
from .supply import validate_supply
from .worldscan import GapCandidate, load_candidates, load_scan_stats, save_candidates, save_scan_stats, scan_world_with_stats
from .worldverify import load_verifications, save_verifications, verify_candidates

app = typer.Typer(no_args_is_help=True, help="Evidence-first market gap radar.")
console = Console()


@app.command("world-scan")
def world_scan_command(
    sources: Path = typer.Option(Path("config/world_sources.yml"), exists=True, readable=True),
    output: Path = typer.Option(Path("data/world-gaps.json")),
    stats_output: Path = typer.Option(Path("data/world-scan-stats.json")),
) -> None:
    """Scan broad news/industry feeds for structural changes that may create market gaps."""
    candidates, stats = scan_world_with_stats(sources)
    save_candidates(output, candidates)
    save_scan_stats(stats_output, stats)
    table = Table(title="GapRadar — World Change Scan")
    table.add_column("Recommendation")
    table.add_column("Type")
    table.add_column("Source")
    table.add_column("Headline")
    for row in candidates[:30]:
        table.add_row(row.recommendation, row.change_type, row.source, row.headline)
    console.print(table)
    console.print(
        f"Raw entries: {stats.raw_entries} · recent: {stats.recent_entries} · structural matches: {stats.structural_matches} · "
        f"deduped candidates: {stats.candidates} · sources ok/failed: {stats.sources_ok}/{stats.sources_failed}"
    )


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
            console.print(f"[green]✓[/green] {source.vendor}/{source.name}: {len(found)} verified event(s), lookback={source.lookback_days}d")
        except Exception as exc:
            failures += 1
            console.print(f"[yellow]![/yellow] {source.vendor}/{source.name}: {exc}")

    merged = merge_events(load_events(output), incoming, revalidate_existing=failures == 0)
    save_events(output, merged)
    console.print(f"\nSources: {len(configured)} · new matches: {len(incoming)} · stored: {len(merged)} · failures: {failures}")


@app.command("world-verify")
def world_verify_command(
    world_gaps: Path = typer.Option(Path("data/world-gaps.json"), exists=True, readable=True),
    events: Path = typer.Option(Path("data/events.json"), exists=True, readable=True),
    output: Path = typer.Option(Path("data/world-verifications.json")),
) -> None:
    """Bridge broad world candidates to verified Tier-1 events without manufacturing facts."""
    candidates = load_candidates(world_gaps)
    verified_events = [event for event in load_events(events) if event.status == "verified" and event.official_evidence]
    rows = verify_candidates(candidates, verified_events)
    save_verifications(output, rows)

    table = Table(title="GapRadar — World Candidate Verification")
    table.add_column("Status")
    table.add_column("Score", justify="right")
    table.add_column("Candidate")
    table.add_column("Official source")
    by_id = {candidate.id: candidate for candidate in candidates}
    for row in rows[:40]:
        candidate = by_id[row.candidate_id]
        table.add_row(row.status, str(row.match_score), candidate.headline[:72], row.official_url or "—")
    verified_count = sum(row.status == "tier1_verified" for row in rows)
    console.print(table)
    console.print(f"Tier-1 bridged: {verified_count}/{len(rows)}. Unverified candidates remain discovery leads only.")


@app.command("validate-demand")
def validate_demand(events: Path = typer.Option(Path("data/events.json"), exists=True, readable=True)) -> None:
    """Search public reaction sources as supporting evidence, not as the primary discovery engine."""
    rows = load_events(events)
    validated = validate_reactions(rows)
    save_events(events, validated)

    table = Table(title="GapRadar — Supporting Demand Evidence")
    table.add_column("Vendor / Product")
    table.add_column("Candidates", justify="right")
    table.add_column("Pain signals", justify="right")
    table.add_column("Demand status")
    table.add_column("Sources")
    for event in validated:
        table.add_row(f"{event.vendor} / {event.product}", str(event.reaction_candidate_count), str(len(event.reaction_evidence)), event.demand_status, ", ".join(event.reaction_sources_checked) or "none")
    console.print(table)


@app.command("validate-supply")
def validate_supply_command(events: Path = typer.Option(Path("data/events.json"), exists=True, readable=True)) -> None:
    """Search replacement supply for every verified event with a demand hypothesis."""
    rows = load_events(events)
    validated = validate_supply(rows)
    save_events(events, validated)

    table = Table(title="GapRadar — Replacement Supply")
    table.add_column("Vendor / Product")
    table.add_column("Candidates", justify="right")
    table.add_column("Accepted", justify="right")
    table.add_column("Supply")
    table.add_column("Gap")
    table.add_column("Sources")
    for event in validated:
        table.add_row(f"{event.vendor} / {event.product}", str(event.supply_candidate_count), str(len(event.supply_evidence)), event.supply_status, event.gap_status, ", ".join(event.supply_sources_checked) or "none")
    console.print(table)


@app.command("backtest")
def backtest_command(
    fixture: Path = typer.Option(Path("data/backtest/events.json"), exists=True, readable=True),
    as_of: str | None = typer.Option(None, "--as-of", help="Replay only events known on or before YYYY-MM-DD."),
    mode: str = typer.Option("fixture", help="fixture = deterministic benchmark; wayback = fetch archived first-party snapshots."),
    output: Path = typer.Option(Path("data/backtest/report.json")),
) -> None:
    """Replay curated historical events and calculate detector precision/recall."""
    if mode not in {"fixture", "wayback"}:
        raise typer.BadParameter("mode must be 'fixture' or 'wayback'")
    parsed_as_of: date | None = None
    if as_of:
        try:
            parsed_as_of = date.fromisoformat(as_of)
        except ValueError as exc:
            raise typer.BadParameter("--as-of must be YYYY-MM-DD") from exc
    report = run_backtest(fixture, as_of=parsed_as_of, mode=mode)  # type: ignore[arg-type]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    metrics = report["metrics"]
    table = Table(title=f"GapRadar — Historical Backtest ({mode})")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    for key in ("cases_total", "cases_evaluated", "archive_unavailable", "tp", "fp", "tn", "fn", "precision", "recall", "event_type_accuracy", "archive_coverage"):
        table.add_row(key, str(metrics.get(key)))
    console.print(table)
    console.print(f"Report written to {output}. Archive misses are reported separately, never converted into detector misses.")


@app.command("blind-backtest")
def blind_backtest_command(
    fixture: Path = typer.Option(Path("data/backtest/events.json"), exists=True, readable=True),
    output: Path = typer.Option(Path("data/backtest/blind-report.json")),
    seed: int = typer.Option(620),
) -> None:
    """Measure WORLD SCAN discovery logic against a shuffled positive/negative historical stream."""
    report = run_blind_backtest(fixture, output, seed=seed)
    metrics = report["metrics"]
    table = Table(title="GapRadar — Blind Noisy-Stream Discovery Benchmark")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    for key in ("cases_total", "tp", "fp", "tn", "fn", "precision", "recall", "event_type_accuracy"):
        table.add_row(key, str(metrics.get(key)))
    console.print(table)
    console.print("This measures discovery logic on a shuffled historical corpus; it is not an all-web retrieval recall claim.")


@app.command("build-dossiers")
def build_dossiers_command(
    events: Path = typer.Option(Path("data/events.json"), exists=True, readable=True),
    output_dir: Path = typer.Option(Path("docs/dossiers")),
    index: Path = typer.Option(Path("data/dossiers.json")),
) -> None:
    """Build human-review opportunity dossiers from verified first-party events."""
    rows = load_events(events)
    dossiers = export_dossiers(rows, output_dir, index)
    table = Table(title="GapRadar — Opportunity Dossiers")
    table.add_column("Vendor / Product")
    table.add_column("Verdict")
    table.add_column("Next action")
    for event, dossier in zip(rows, dossiers):
        table.add_row(f"{event.vendor} / {event.product}", dossier.verdict, dossier.next_action)
    console.print(table)
    console.print(f"Dossiers: {len(dossiers)} · markdown/json: {output_dir} · index: {index}")


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
        row: dict[str, object] = {"vendor": source.vendor, "name": source.name, "url": source.url, "checked_at": checked_at}
        try:
            result = probe_source(source)
            healthy = result.entry_count > 0 and result.official_link_count > 0
            if not healthy:
                failures += 1
            row.update(status="ok" if healthy else "bad_feed", http_status=result.http_status, entry_count=result.entry_count, official_link_count=result.official_link_count, error=None)
            table.add_row(f"{source.vendor}/{source.name}", str(result.http_status), str(result.entry_count), str(result.official_link_count), "OK" if healthy else "BAD FEED")
        except Exception as exc:
            failures += 1
            row.update(status="error", http_status=None, entry_count=0, official_link_count=0, error=f"{type(exc).__name__}: {exc}")
            table.add_row(f"{source.vendor}/{source.name}", "—", "0", "0", f"ERROR: {exc}")
        rows.append(row)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    console.print(table)
    console.print(f"Health snapshot written to {output}. Failures: {failures}.")
    if strict and failures:
        raise typer.Exit(code=2)


@app.command()
def report(events: Path = typer.Option(Path("data/events.json"), exists=True, readable=True)) -> None:
    """Render a compact evidence-aware event report."""
    rows = load_events(events)
    table = Table(title="GapRadar — Verified Market Changes")
    table.add_column("Type")
    table.add_column("Vendor / Product")
    table.add_column("Confidence")
    table.add_column("Demand")
    table.add_column("Supply")
    table.add_column("Gap")
    table.add_column("Headline")
    for event in rows:
        table.add_row(event.event_type.value, f"{event.vendor} / {event.product}", event.confidence.value, event.demand_status, event.supply_status, event.gap_status, event.headline)
    console.print(table)


def _apply_world_verification(candidates: list[GapCandidate], verification_path: Path) -> list[GapCandidate]:
    verifications = load_verifications(verification_path)
    if not verifications:
        return [
            replace(
                candidate,
                recommendation="WATCH",
                validation_status="UNVERIFIED",
                validation_summary="No Tier-1 bridge result is available. This item is a discovery lead only and cannot be presented as a verified market gap.",
            )
            for candidate in candidates
        ]

    rows: list[GapCandidate] = []
    for candidate in candidates:
        verification = verifications.get(candidate.id)
        if verification and verification.status == "tier1_verified":
            rows.append(
                replace(
                    candidate,
                    validation_status="TIER-1 VERIFIED",
                    validation_summary=f"Matched to verified first-party event {verification.event_id} with evidence score {verification.match_score}. Official source: {verification.official_url}",
                )
            )
        else:
            rows.append(
                replace(
                    candidate,
                    recommendation="WATCH",
                    validation_status="UNVERIFIED",
                    validation_summary="No sufficiently strong Tier-1 event match. Keep as a world-change lead; do not infer an investable or buildable market gap yet.",
                )
            )
    return rows


@app.command("export")
def export_dashboard(
    events: Path = typer.Option(Path("data/events.json")),
    world_gaps: Path = typer.Option(Path("data/world-gaps.json")),
    world_stats: Path = typer.Option(Path("data/world-scan-stats.json")),
    world_verifications: Path = typer.Option(Path("data/world-verifications.json")),
    output: Path = typer.Option(Path("docs/index.html")),
) -> None:
    """Export the standalone opportunity board with Tier-1 verification guardrails."""
    rows = load_events(events)
    candidates = _apply_world_verification(load_candidates(world_gaps), world_verifications)
    stats = load_scan_stats(world_stats)
    render_dashboard(rows, output, candidates, stats)
    verified_world = sum(candidate.validation_status == "TIER-1 VERIFIED" for candidate in candidates)
    console.print(
        f"Opportunity board exported to {output} with {len(candidates)} world candidate(s), "
        f"{verified_world} Tier-1 bridged world lead(s), and {len(rows)} verified event(s)."
    )


if __name__ == "__main__":
    app()

# Historical Backtest Corpus

This directory is a deliberately small, inspectable benchmark for GapRadar. It exists to stop architectural confidence from being mistaken for empirical accuracy.

## What is in `events.json`

The corpus currently contains 24 manually curated cases: 18 known market-change events and 6 negative controls. Cases span shutdown/EOL, pricing or free-tier shocks, API/platform-policy changes, licensing changes, and reversal/retraction examples.

Each positive case records:

- the vendor and affected product;
- the historical event date and replay `as_of` date;
- the expected event class;
- a first-party announcement URL;
- a short title/excerpt fixture used only by deterministic fixture mode;
- manually labeled displaced-demand and replacement-supply ground truth;
- retraction metadata when known.

Negative controls are ordinary official product/news pages that should not become market-change events.

## Two benchmark modes

### Fixture mode

`gapradar backtest --mode fixture`

Runs the detector against the curated historical title/excerpt fixtures. It is deterministic and is suitable for regression testing precision, recall and event-type classification.

These numbers are **benchmark metrics, not universal market accuracy**. The corpus is small and hand curated.

### Wayback mode

`gapradar backtest --mode wayback`

Uses the Internet Archive CDX API to find the closest official first-party page snapshot at or before each case's historical `replay_as_of` date, then runs the detector against the archived HTML.

Wayback availability is part of the report. A missing or unreachable archive snapshot is recorded as `archive_missing` / `archive_error`; it is never silently converted into a detector false negative.

## `--as-of`

The benchmark can be truncated to a historical point in time:

```bash
gapradar backtest --as-of 2023-12-31 --mode fixture
```

Future cases are excluded rather than leaked into the replay.

## Current boundary

V0.7 measures the **event-detection / verification layer** against historical evidence. The fixture already carries ground-truth demand and supply labels, but downstream reaction/supply precision is not counted until archived reaction and replacement evidence is attached to those cases. A report must not describe those labels as measured demand/supply accuracy yet.

That boundary is intentional: an incomplete historical source is reported as incomplete instead of being turned into a confident score.

## Label discipline

- First-party announcements establish the event fact.
- Ground-truth demand/supply labels are manual benchmark annotations, not generated model scores.
- A retracted event remains useful history; it is marked explicitly rather than deleted from the corpus.
- Failures and misses stay visible in reports.

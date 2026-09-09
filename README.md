# GapRadar

**Detect verified market changes before they become obvious opportunities.**

GapRadar watches first-party software sources for shutdowns, end-of-life notices, pricing shocks, API deprecations, and major platform-policy changes. It then validates displaced demand, checks replacement supply, and produces an evidence-grounded opportunity dossier instead of a generic startup idea.

> Market changes can create displaced demand. GapRadar detects the change first, then earns the right to investigate the gap.

## The model

```text
DETECT → VERIFY → REACTION → SUPPLY → GAP → DOSSIER
                    ↕
             HISTORICAL BACKTEST
```

A vendor announcement proves a change happened. Community reaction can show whether users are actually displaced. Replacement supply can show whether that displaced demand is already served. The dossier summarizes only the evidence that survived those gates.

## V0.7 — historical backtest

V0.7 stops treating architecture quality as evidence of accuracy. GapRadar now has a historical replay harness that can test the detector against known market changes and, where benchmark evidence exists, replay the same reaction and supply scorers against historical documents.

It includes:

- a curated corpus of **24 historical cases**: 18 known market-change events plus 6 negative controls;
- shutdown/EOL, free-tier and pricing shocks, API/platform-policy changes, licensing changes and reversal cases;
- manually recorded ground-truth event date, event class, displaced-demand label, replacement-supply label and retraction metadata where known;
- `gapradar backtest --as-of YYYY-MM-DD` so future cases cannot leak into a historical replay;
- deterministic fixture mode for regression testing;
- Wayback mode that asks the Internet Archive for the closest first-party snapshot at or before the historical replay date;
- separate archive coverage reporting: an unavailable snapshot is **not** silently converted into a detector miss;
- archived reaction evidence scored by the same migration-pain logic used live;
- archived replacement pages scored by the same supply logic used live;
- a starter downstream corpus covering Heroku, Docker Free Team, Unity Runtime Fee and Reddit API reactions, plus replacement evidence for Heroku, Docker and Unity;
- a dedicated `Historical Backtest` GitHub Action that prints and uploads both fixture and Wayback reports.

Historical full-page recall rules are isolated from the live feed scanner. This matters: an early V0.7 experiment broadened body matching enough to incorrectly classify Shopify's **“Oxygen is now available on trial plan stores”** as a price shock because its text mentioned that hosting had previously required a paid plan. The historical rules are now explicitly opt-in, and the live scanner has a regression test preventing that class of false positive.

The event store also revalidates persisted events after a clean source scan, so a false positive that no longer passes current live rules is removed rather than living forever in `data/events.json`. If any live source fails, pruning is disabled for that run so a temporary outage cannot delete valid history.

### Run the benchmark

```bash
# Deterministic curated benchmark
gapradar backtest \
  --mode fixture \
  --output data/backtest/report-fixture.json

# Replay only history known by a date
gapradar backtest \
  --as-of 2023-12-31 \
  --mode fixture

# Fetch archived first-party/reaction/supply pages
gapradar backtest \
  --mode wayback \
  --output data/backtest/report-wayback.json
```

The report exposes TP / FP / TN / FN, precision, recall, event-type accuracy and archive coverage. Demand/supply accuracy is shown only for cases that actually have benchmark evidence pages and, in Wayback mode, only when those pages were retrievable. A small downstream sample must not be presented as universal market accuracy.

See `data/backtest/README.md` for benchmark methodology and boundaries.

## Evidence hierarchy

| Tier | Purpose | Examples | Can verify the event? |
| --- | --- | --- | --- |
| Tier 1 — Official | Establish the fact | vendor changelog, official blog, developer docs | **Yes** |
| Tier 2 — Reaction | Measure displaced demand | HN, GitHub issues, forums | No |
| Tier 3 — Supply | Measure replacement supply | GitHub repositories, npm packages, competing products | No |

**No Tier-1 source = no verified event. Tier-2 and Tier-3 evidence can only evaluate a verified event.**

## Demand states

- `unassessed` — demand search has not run or the search failed;
- `no_signal` — the recorded queries completed but no qualifying migration-pain signal was detected;
- `early_signal` — at least one qualifying displaced-demand reaction;
- `repeated_signal` — at least three qualifying displaced-demand reactions.

`no_signal` is a detection result, not a market truth.

## Supply states

- `unassessed`
- `no_supply`
- `thin_supply`
- `served`

Supply validation is skipped unless demand survives the reaction gate.

## Gap states

- `unassessed`
- `watch`
- `potential_gap`
- `likely_served`

A `potential_gap` is still not a command to build. It is the first state that earns a `REVIEW` dossier.

## Dossier verdicts

- `NO DETECTED SIGNAL` — the current audited search found no qualifying displaced-demand evidence; this does **not** mean demand is absent;
- `SEARCH FAILED` — reaction search did not complete and no demand conclusion is allowed;
- `WATCH` — some evidence exists, but the chain is incomplete or still early;
- `REVIEW` — repeated displaced demand survived the supply check and deserves human opportunity review;
- `LIKELY SERVED` — displaced demand exists, but credible replacement supply already looks strong;
- `INSUFFICIENT EVIDENCE` — the event itself is not adequately verified.

GapRadar is explicitly allowed to say **we did not detect demand yet** without pretending that means **there is no demand**.

## Current live sources and boundary

First-party events: GitHub, Shopify, Slack, Cloudflare.  
Reaction: Hacker News and GitHub Issues.  
Supply: GitHub repositories and npm.

This is **not an all-web radar**. Its current live event coverage is intentionally narrow while precision and recall are being measured. A change announced only by an unmonitored vendor can be missed completely.

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest

gapradar doctor
gapradar scan
gapradar validate-demand
gapradar validate-supply
gapradar build-dossiers
gapradar report
gapradar export
gapradar backtest --mode fixture
```

The daily GitHub Action runs the live chain and commits refreshed events, source health, dossiers, and dashboard output. The Historical Backtest workflow is separate so archive availability never blocks the live radar.

## Guardrails

1. **No official source, no verified event.**
2. Community reaction can never create a Tier-1 fact.
3. Popular discussion is not displaced demand unless it contains migration pain tied to the affected product.
4. A failed search cannot become `no_signal`.
5. `no_signal` means “not detected by these queries”, never “no demand exists”.
6. Popular software is not replacement supply unless it is relevant to the affected product.
7. Supply analysis is skipped when an event fails the demand gate.
8. `REVIEW` requires repeated demand that survives the supply check.
9. Dossiers summarize evidence; they do not fabricate market size, revenue forecasts, opportunity scores, or build windows.
10. Archive failure is archive failure, not detector failure.
11. Fixture accuracy is benchmark accuracy, not a claim about the whole market.
12. Historical recall rules may not silently weaken live precision.

## Repository layout

```text
config/sources.yml             first-party live source registry
src/gapradar/detector.py       live + historical hard-event detection
src/gapradar/reaction.py       auditable reaction search + archived reaction scorer
src/gapradar/supply.py         live supply search + archived supply scorer
src/gapradar/backtest.py       as-of / fixture / Wayback replay engine
src/gapradar/dossier.py        evidence-grounded opportunity dossier builder
src/gapradar/models.py         evidence, search quality, demand, supply and gap state
src/gapradar/store.py          persistence + stale-event revalidation
src/gapradar/cli.py            radar commands
data/backtest/events.json      historical event + negative-control corpus
data/backtest/downstream.json  historical reaction/supply evidence corpus
data/backtest/README.md        benchmark methodology
data/events.json               verified live event state + reaction query audit
data/dossiers.json             generated dossier index
docs/dossiers/                 per-event Markdown + JSON dossiers
docs/index.html                generated dashboard
.github/workflows/             CI + live radar + historical backtest
tests/                         precision, recall and false-positive regression tests
```

## Roadmap

**V0.1 — Hard-event skeleton** ✅  
**V0.2 — Precision-first live radar** ✅  
**V0.3 — Displaced-demand validation** ✅  
**V0.4 — Supply-gap analysis** ✅  
**V0.5 — Opportunity dossier** ✅  
**V0.6 — Auditable demand search** ✅  
**V0.7 — Historical backtest framework** ✅

The next work should increase **benchmark coverage before product surface area**: more independently verifiable historical reaction/supply evidence, more negative controls, retraction replay, then low-cost Tier-1 coverage expansion such as shared changelog/status platforms. It should not add fake intelligence scores.

## License

MIT © 2026 Amazing Kimi

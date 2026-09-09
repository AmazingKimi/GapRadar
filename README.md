# GapRadar

**Detect verified market changes before they become obvious opportunities.**

GapRadar watches first-party software sources for shutdowns, end-of-life notices, pricing shocks, API deprecations, and major platform-policy changes. It then validates displaced demand, checks replacement supply, and produces an evidence-grounded opportunity dossier instead of a generic startup idea.

> Market changes can create displaced demand. GapRadar detects the change first, then earns the right to investigate the gap.

## The model

```text
DETECT → VERIFY → REACTION → SUPPLY → GAP → DOSSIER
```

A vendor announcement proves a change happened. Community reaction can show whether users are actually displaced. Replacement supply can show whether that displaced demand is already served. The dossier summarizes only the evidence that survived those gates.

## V0.6 — auditable demand search

V0.6 fixes the highest-leverage weakness in V0.5: reaction search could be too narrow, and `no_signal` was being presented too much like evidence of no demand.

It now:

- runs multiple reaction queries per event instead of one narrow vendor+product query;
- includes broad product queries plus event-language queries such as deprecation, migration and alternatives;
- records every query, source, success/failure state and raw candidate count;
- deduplicates candidates across query variants before scoring migration pain;
- rejects generic keyword noise unless the affected product/vendor is actually present;
- marks reaction-search quality as `adequate`, `degraded`, `failed` or `unassessed`;
- refuses to convert a failed search into `no_signal`;
- treats `no_signal` as **no detected signal**, not proof that demand is absent;
- leaves the gap state `unassessed` when no demand signal was detected;
- keeps the V0.5 demand gate, so supply search still runs only after displaced demand survives;
- exposes the query audit in each opportunity dossier and the dashboard.

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

## Current live sources

First-party events: GitHub, Shopify, Slack, Cloudflare.  
Reaction: Hacker News and GitHub Issues.  
Supply: GitHub repositories and npm.

The source set is intentionally narrow while precision and recall are being hardened.

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
```

The daily GitHub Action runs the full chain and commits refreshed events, source health, dossiers, and dashboard output back to the repository.

## Guardrails

1. **No official source, no verified event.**
2. Community reaction can never create a Tier-1 fact.
3. Popular discussion is not displaced demand unless it contains migration pain tied to the affected product.
4. A failed search cannot become `no_signal`.
5. `no_signal` means "not detected by these queries", never "no demand exists".
6. Popular software is not replacement supply unless it is relevant to the affected product.
7. Supply analysis is skipped when an event fails the demand gate.
8. `REVIEW` requires repeated demand that survives the supply check.
9. Dossiers summarize evidence; they do not fabricate market size, revenue forecasts, opportunity scores, or build windows.

## Repository layout

```text
config/sources.yml          first-party source registry
src/gapradar/detector.py    hard-event detection and official-domain guardrails
src/gapradar/reaction.py    multi-query displaced-demand search, audit and filtering
src/gapradar/supply.py      replacement-supply search and filtering
src/gapradar/dossier.py     evidence-grounded opportunity dossier builder
src/gapradar/models.py      evidence, search quality, demand, supply and gap state model
src/gapradar/cli.py         radar commands
data/events.json            verified event state + reaction query audit
data/dossiers.json          generated dossier index
docs/dossiers/              per-event Markdown + JSON dossiers
docs/index.html             generated dashboard
.github/workflows/          CI + daily live radar
tests/                      precision, recall and false-positive regression tests
```

## Roadmap

**V0.1 — Hard-event skeleton** ✅  
**V0.2 — Precision-first live radar** ✅  
**V0.3 — Displaced-demand validation** ✅  
**V0.4 — Supply-gap analysis** ✅  
**V0.5 — Opportunity dossier** ✅  
**V0.6 — Auditable demand search** ✅

Next coverage work should add more reaction sources and validate recall against known historical displacement events. It should not add fake intelligence scores.

## License

MIT © 2026 Amazing Kimi

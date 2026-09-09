# GapRadar

**Detect verified market changes before they become obvious opportunities.**

GapRadar watches first-party software sources for shutdowns, end-of-life notices, pricing shocks, API deprecations, and major platform-policy changes. It then validates whether real users appear to be displaced and whether credible replacement supply already exists.

> Market changes can create displaced demand. GapRadar detects the change first, then earns the right to investigate the gap.

## The model

```text
DETECT → VERIFY → TRIAGE → REACTION → SUPPLY → POTENTIAL GAP
```

A vendor announcement proves a change happened. Community reaction can show whether users are actually displaced. Replacement supply can show whether that displaced demand is already served. Only after both downstream checks should a gap be considered.

## V0.4 — supply-gap analysis

V0.4 keeps the precision-first event radar and displaced-demand validation from V0.3, then adds a real Tier-3 replacement-supply stage.

It currently:

- scans official first-party feeds for hard market changes;
- searches Hacker News and GitHub Issues for forced migration and replacement pain;
- searches GitHub repositories and npm for plausible replacement supply;
- scores supply by relevance, freshness, popularity, activity and explicit replacement language;
- rejects irrelevant popular projects that merely share generic words;
- penalizes archived replacement projects;
- deduplicates candidates and preserves source provenance;
- records how many reaction and supply candidates were inspected even when zero qualify;
- classifies both demand and supply before assigning a gap state;
- persists the full evidence chain to `data/events.json`;
- regenerates `docs/index.html` with demand, supply and gap states;
- runs the complete pipeline automatically in GitHub Actions every day;
- emits no invented market-size, revenue or opportunity percentage.

## Evidence hierarchy

| Tier | Purpose | Examples | Can verify the event? |
| --- | --- | --- | --- |
| Tier 1 — Official | Establish the fact | vendor changelog, official blog, developer docs | **Yes** |
| Tier 2 — Reaction | Measure displaced demand | HN, GitHub issues, forums | No |
| Tier 3 — Supply | Measure replacement supply | GitHub repositories, npm packages, competing products | No |

**No Tier-1 source = no verified event. Tier-2 and Tier-3 evidence can only evaluate a verified event.**

## Demand states

- `unassessed` — reaction validation has not run;
- `no_signal` — checked sources produced no qualifying migration-pain evidence;
- `early_signal` — at least one qualifying displaced-demand reaction;
- `repeated_signal` — at least three qualifying displaced-demand reactions.

High engagement can strengthen a reaction, but engagement alone is never enough.

## Supply states

- `unassessed` — replacement-supply validation has not run;
- `no_supply` — checked sources produced no qualifying replacement candidate;
- `thin_supply` — at least one plausible replacement exists, but the evidence does not yet look mature or crowded;
- `served` — several plausible replacements exist or one candidate is unusually strong.

A repository or package is not accepted just because it is popular. It must match the affected product closely enough to survive the relevance filter.

## Gap states

GapRadar deliberately separates **event**, **demand**, **supply**, and **gap**.

- `unassessed` — downstream validation is incomplete;
- `no_demand` — a real change happened, but no displaced-demand signal was found;
- `watch` — some demand exists, but evidence is still early or supply is unclear;
- `potential_gap` — repeated displaced demand exists while replacement supply is absent or thin;
- `likely_served` — displaced demand exists, but replacement supply already looks strong.

A `potential_gap` is still not a command to build. It is the first state that deserves a human opportunity review.

## Current live sources

First-party event sources currently include:

- GitHub
- Shopify
- Slack
- Cloudflare

Reaction sources:

- Hacker News via the public Algolia API
- GitHub Issues via GitHub Search

Supply sources:

- GitHub repositories via GitHub Search
- npm registry search

The supply layer is intentionally developer-market biased in V0.4. Broader SaaS directories and app marketplaces belong in later coverage expansion, not in the first working supply model.

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
gapradar report
gapradar export
```

The daily GitHub Action runs those stages in the same order and commits refreshed event state and dashboard output back to the repository.

## Guardrails

1. **No official source, no verified event.**
2. Community reaction can never create a Tier-1 fact.
3. Popular discussion is not displaced demand unless it contains migration pain tied to the affected product.
4. Popular software is not replacement supply unless it is relevant to the affected product.
5. Archived projects are penalized rather than treated as healthy alternatives.
6. `no_signal` and `no_supply` are valid outcomes; the system is allowed to find nothing.
7. A `potential_gap` requires repeated demand plus absent/thin replacement supply.
8. No fake `Opportunity Score: 91/100`, market size, revenue forecast or arbitrary opportunity window.

## Repository layout

```text
config/sources.yml          first-party source registry
src/gapradar/detector.py    hard-event detection and official-domain guardrails
src/gapradar/reaction.py    displaced-demand search, scoring and deduplication
src/gapradar/supply.py      replacement-supply search, scoring and deduplication
src/gapradar/models.py      evidence, demand, supply and gap state model
src/gapradar/store.py       persistent event store
src/gapradar/cli.py         scan / validate-demand / validate-supply / report / export
src/gapradar/render.py      static evidence dashboard
data/events.json            complete verified event state
data/source-health.json     latest first-party source health
docs/index.html             generated dashboard
.github/workflows/          CI + daily live radar
tests/                      precision and false-positive regression tests
```

## Roadmap

**V0.1 — Hard-event skeleton** ✅  
Evidence model, classifier, persistence, CLI, scheduled scan, CI.

**V0.2 — Precision-first live radar** ✅  
Real first-party feeds, source health, bounded lookback, false-positive regression tests.

**V0.3 — Displaced-demand validation** ✅  
Live reaction search, migration-pain filtering, deduplication, provenance, demand states.

**V0.4 — Supply-gap analysis** ✅  
Live GitHub/npm replacement search, relevance and activity scoring, supply states, gap states, dashboard integration, daily automation.

**V0.5 — Opportunity dossier**  
Produce a fully cited human-review dossier: what changed, who appears displaced, which substitutes exist, what remains unsolved, and why the gap may or may not be worth building for.

## License

MIT © 2026 Amazing Kimi

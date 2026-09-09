# GapRadar

**Detect verified market changes before they become obvious opportunities.**

GapRadar watches first-party software sources for shutdowns, end-of-life notices, pricing shocks, API deprecations, and major platform-policy changes. It then validates displaced demand, checks replacement supply, and produces an evidence-grounded opportunity dossier instead of a generic startup idea.

> Market changes can create displaced demand. GapRadar detects the change first, then earns the right to investigate the gap.

## The model

```text
DETECT → VERIFY → REACTION → SUPPLY → GAP → DOSSIER
```

A vendor announcement proves a change happened. Community reaction can show whether users are actually displaced. Replacement supply can show whether that displaced demand is already served. The dossier summarizes only the evidence that survived those gates.

## V0.5 — opportunity dossiers

V0.5 turns the V0.4 evidence chain into a human-review artifact for every verified event.

Each dossier answers:

- what changed and where the first-party evidence is;
- whether real migration pain was found;
- which replacement products or projects survived relevance filtering;
- what, if anything, still appears unsolved;
- whether the current evidence says `REVIEW`, `WATCH`, `PASS`, `LIKELY SERVED`, or `INSUFFICIENT EVIDENCE`;
- the next evidence-gathering action without inventing market size, revenue, or arbitrary opportunity percentages.

Dossiers are generated as both Markdown and JSON under `docs/dossiers/`, with a machine-readable index in `data/dossiers.json`. The dashboard surfaces the verdict and links to the full dossier.

## Evidence hierarchy

| Tier | Purpose | Examples | Can verify the event? |
| --- | --- | --- | --- |
| Tier 1 — Official | Establish the fact | vendor changelog, official blog, developer docs | **Yes** |
| Tier 2 — Reaction | Measure displaced demand | HN, GitHub issues, forums | No |
| Tier 3 — Supply | Measure replacement supply | GitHub repositories, npm packages, competing products | No |

**No Tier-1 source = no verified event. Tier-2 and Tier-3 evidence can only evaluate a verified event.**

## Decision gates

Demand states:

- `unassessed`
- `no_signal`
- `early_signal`
- `repeated_signal`

Supply states:

- `unassessed`
- `no_supply`
- `thin_supply`
- `served`

Gap states:

- `unassessed`
- `no_demand`
- `watch`
- `potential_gap`
- `likely_served`

A `potential_gap` is still not a command to build. It is the first state that earns a `REVIEW` dossier.

## Dossier verdicts

- `PASS` — the market change is real, but no qualifying displaced-demand evidence was found;
- `WATCH` — some evidence exists, but the chain is incomplete or still early;
- `REVIEW` — repeated displaced demand survived the supply check and deserves human opportunity review;
- `LIKELY SERVED` — displaced demand exists, but credible replacement supply already looks strong;
- `INSUFFICIENT EVIDENCE` — the event itself is not adequately verified.

GapRadar is explicitly allowed to say **do not build this**.

## Current live sources

First-party events: GitHub, Shopify, Slack, Cloudflare.  
Reaction: Hacker News and GitHub Issues.  
Supply: GitHub repositories and npm.

The source set is intentionally narrow while precision is being hardened.

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
4. Popular software is not replacement supply unless it is relevant to the affected product.
5. Supply analysis is skipped when an event fails the demand gate.
6. Silence, `PASS`, and `no_signal` are valid outcomes.
7. `REVIEW` requires repeated demand that survives the supply check.
8. Dossiers summarize evidence; they do not fabricate market size, revenue forecasts, opportunity scores, or build windows.

## Repository layout

```text
config/sources.yml          first-party source registry
src/gapradar/detector.py    hard-event detection and official-domain guardrails
src/gapradar/reaction.py    displaced-demand search and filtering
src/gapradar/supply.py      replacement-supply search and filtering
src/gapradar/dossier.py     evidence-grounded opportunity dossier builder
src/gapradar/models.py      evidence, demand, supply and gap state model
src/gapradar/cli.py         radar commands
data/events.json            verified event state
data/dossiers.json          generated dossier index
docs/dossiers/              per-event Markdown + JSON dossiers
docs/index.html             generated dashboard
.github/workflows/          CI + daily live radar
tests/                      precision and false-positive regression tests
```

## Roadmap

**V0.1 — Hard-event skeleton** ✅  
**V0.2 — Precision-first live radar** ✅  
**V0.3 — Displaced-demand validation** ✅  
**V0.4 — Supply-gap analysis** ✅  
**V0.5 — Opportunity dossier** ✅

V0.6 should focus on broader source coverage and dossier-quality validation, not on adding fake intelligence scores.

## License

MIT © 2026 Amazing Kimi

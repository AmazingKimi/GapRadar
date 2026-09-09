# GapRadar

**Detect verified market changes before they become obvious opportunities.**

GapRadar watches first-party software sources for shutdowns, end-of-life notices, pricing shocks, API deprecations, and major platform-policy changes. It then validates whether real users appear to be displaced by searching public reaction sources for migration pain rather than ordinary discussion.

> Market changes can create displaced demand. GapRadar detects the change first, then earns the right to investigate the gap.

## The model

```text
DETECT → VERIFY → TRIAGE → REACTION → SUPPLY → POTENTIAL GAP
```

The key distinction is between a **fact** and an **opportunity**.

- A vendor announcement can prove that a product, price, API, or policy changed.
- Community reaction can show whether users are actually displaced.
- Replacement supply can show whether the displaced demand is already served.
- Only after those stages should a business opportunity be considered.

## V0.3 — displaced-demand validation

V0.3 keeps the precision-first V0.2 radar and adds a real Tier-2 reaction stage.

It currently:

- polls configured first-party RSS/Atom feeds;
- accepts only links on an explicit official-domain allowlist;
- limits scans to a recent lookback window;
- detects three hard-event families;
- rejects incidental deprecation mentions inside unrelated feature announcements;
- searches **Hacker News** and **GitHub Issues** for reactions to each verified event;
- distinguishes forced migration / replacement search / switching pain from ordinary product discussion;
- deduplicates reaction URLs and preserves source provenance;
- records how many reaction candidates were checked even when the result is zero;
- persists verified events and reaction evidence to `data/events.json`;
- records live first-party source health in `data/source-health.json`;
- regenerates a standalone dashboard at `docs/index.html`;
- runs the complete pipeline automatically in GitHub Actions every day;
- keeps scanning when one source is temporarily unavailable;
- emits no fake numerical opportunity score.

### Event families

| Event | Examples |
| --- | --- |
| **Shutdown / EOL** | product retirement, feature removal, support ending, service shutdown |
| **Price Shock** | major price change, free-tier removal, billing model change |
| **API / Terms Change** | API deprecation, endpoint removal, breaking policy/terms change |

### Evidence hierarchy

| Tier | Purpose | Examples | Can verify the event? |
| --- | --- | --- | --- |
| Tier 1 — Official | Establish the fact | vendor changelog, official blog, developer docs | **Yes** |
| Tier 2 — Reaction | Measure displaced demand | HN, GitHub issues, forums | No |
| Tier 3 — Supply | Measure replacement quality | directories, app stores, competing products | No |

**No Tier-1 source = no verified event. Tier-2 reaction can strengthen a verified event, but can never create one.**

## What counts as displaced-demand evidence

V0.3 intentionally does not count every mention, complaint, or popular discussion as demand.

A public reaction is retained only when it is tied to the affected product and contains enough evidence of things such as:

- forced migration;
- switching or moving away;
- searching for a replacement or alternative;
- a workaround becoming necessary;
- the old path no longer working;
- explicit frustration, blocking, cost, or breakage caused by the change.

High engagement can strengthen a reaction, but engagement alone is never enough.

Demand state is deliberately categorical:

- `unassessed` — reaction validation has not run;
- `no_signal` — sources were checked, but no qualifying migration-pain evidence was found;
- `early_signal` — at least one qualifying reaction was found;
- `repeated_signal` — at least three qualifying reactions were found.

These are evidence states, not claims about market size or revenue.

## Why the detector remains conservative

A real feed creates a nasty false-positive problem. A feature announcement can casually say an old field is deprecated; a release note can mention a migration; a new SDK can discuss older APIs. Those are not automatically market gaps.

GapRadar therefore uses a precision-first rule:

1. explicit change language in the title is eligible;
2. body-only matches are allowed only for titles framed as migration, transition, removal, end-of-support, or sunset notices;
3. the linked evidence must remain on the source's official domain;
4. old entries outside the configured lookback window are ignored;
5. Tier-2 reactions must mention the affected product and show migration pain, not mere discussion.

The project prefers missing a weak signal over telling someone to build a product around noise.

## Current first-party sources

The registry in [`config/sources.yml`](config/sources.yml) currently includes developer/product feeds from:

- GitHub
- Shopify
- Slack
- Cloudflare

The source list is intentionally small while precision is being hardened. Adding hundreds of noisy feeds is not progress.

## Current reaction sources

V0.3 searches:

- Hacker News through the public Algolia search API;
- GitHub Issues through the public GitHub search API.

The reaction layer is designed as a separate stage so additional community sources can be added without weakening Tier-1 verification.

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
gapradar report
gapradar export
```

`gapradar doctor` probes every configured official feed and writes a machine-readable health snapshot. `gapradar scan` stores verified hard events. `gapradar validate-demand` searches public reactions and keeps only qualifying migration-pain evidence. `gapradar export` rebuilds the static dashboard.

## Confidence is evidence confidence, not business confidence

GapRadar does **not** output invented claims such as `Opportunity Score: 91/100` or `Window: 3–6 months`.

Current labels mean:

- `weak` — the hard event has official verification, but no qualifying downstream demand evidence yet;
- `emerging` — official event plus at least one migration-pain reaction;
- `strong` — repeated reaction plus replacement/supply evidence;
- `insufficient_evidence` — no qualifying first-party verification.

V0.3 can reach `emerging`, but `strong` still requires the Tier-3 supply stage planned for V0.4.

## Repository layout

```text
config/sources.yml          first-party source registry
src/gapradar/detector.py    feed parsing, hard-event detection, domain guardrails
src/gapradar/reaction.py    reaction search, pain scoring, deduplication, provenance
src/gapradar/models.py      evidence/event/demand-state model
src/gapradar/store.py       persistent event store and downstream-evidence preservation
src/gapradar/cli.py         scan / validate-demand / doctor / report / export commands
src/gapradar/render.py      static radar dashboard
data/events.json            verified event + reaction state
data/source-health.json     latest source-health snapshot
docs/index.html             generated dashboard
.github/workflows/          CI + daily live radar
tests/                      detector, evidence and reaction guardrail tests
```

## Guardrails

1. **No official source, no verified event.**
2. HN, GitHub issues, Reddit, social posts, and directories can never become Tier 1 evidence.
3. A popular discussion is not displaced demand unless it contains migration-pain evidence tied to the affected product.
4. A GitHub repository being archived is not by itself proof of displaced demand.
5. Detection and commercial evaluation are separate stages.
6. One failing source must not stop the rest of the radar.
7. Incidental words such as “deprecated” in an unrelated announcement must not create an event.
8. Silence is a valid result.

## Roadmap

**V0.1 — Hard-event skeleton**  
Evidence model, initial classifier, persistence, CLI, scheduled scan, CI.

**V0.2 — Precision-first live radar** ✅  
Real first-party feeds, source health, bounded lookback, live GitHub Action runs, false-positive regression tests, generated dashboard.

**V0.3 — Displaced-demand validation** ✅  
Live HN + GitHub Issues reaction search, migration-pain filtering, deduplication, provenance, demand states, dashboard visibility, regression tests.

**V0.4 — Supply-gap analysis**  
Map existing substitutes and determine whether displaced demand is already well served.

**V0.5 — Opportunity dossier**  
Produce a fully cited human-review dossier: what changed, who appears displaced, what substitutes exist, what remains unsolved, and why the gap may or may not be worth building for.

## License

MIT © 2026 Amazing Kimi

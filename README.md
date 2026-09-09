# GapRadar

**Detect verified market changes before they become obvious opportunities.**

GapRadar watches first-party software sources for shutdowns, end-of-life notices, pricing shocks, API deprecations, and major platform-policy changes. It is deliberately evidence-first: a market event is not treated as an opportunity just because an AI can tell a convincing story about it.

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

## V0.2 — precision-first live radar

V0.2 is a working automated radar, not a sample-data demo.

It currently:

- polls configured first-party RSS/Atom feeds;
- accepts only links on an explicit official-domain allowlist;
- limits scans to a recent lookback window;
- detects three hard-event families;
- rejects incidental deprecation mentions inside unrelated feature announcements;
- persists verified events to `data/events.json`;
- records live source health in `data/source-health.json`;
- regenerates a standalone dashboard at `docs/index.html`;
- runs automatically in GitHub Actions every day;
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
| Tier 2 — Reaction | Measure displaced demand | forums, HN, Reddit, GitHub issues | No |
| Tier 3 — Supply | Measure replacement quality | directories, app stores, competing products | No |

**No Tier-1 source = no verified event.**

## Why the detector is conservative

A real feed creates a nasty false-positive problem. A feature announcement can casually say an old field is deprecated; a release note can mention a migration; a new SDK can discuss older APIs. Those are not automatically market gaps.

V0.2 therefore uses a precision-first rule:

1. explicit change language in the title is eligible;
2. body-only matches are allowed only for titles framed as migration, transition, removal, end-of-support, or sunset notices;
3. the linked evidence must remain on the source's official domain;
4. old entries outside the configured lookback window are ignored.

The project prefers missing a weak signal over telling someone to build a product around noise.

## Current first-party sources

The registry in [`config/sources.yml`](config/sources.yml) currently includes developer/product feeds from:

- GitHub
- Shopify
- Slack
- Cloudflare

The source list is intentionally small while precision is being hardened. Adding hundreds of noisy feeds is not progress.

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest

gapradar doctor
gapradar scan
gapradar report
gapradar export
```

`gapradar doctor` probes every configured official feed and writes a machine-readable health snapshot. `gapradar scan` stores verified matches. `gapradar export` rebuilds the static dashboard.

## Confidence is evidence confidence, not business confidence

GapRadar does **not** output invented claims such as `Opportunity Score: 91/100` or `Window: 3–6 months`.

Current labels mean:

- `weak` — the hard event has official verification, but no downstream demand evidence yet;
- `emerging` — official event plus at least one reaction signal;
- `strong` — repeated reaction plus replacement/supply evidence;
- `insufficient_evidence` — no qualifying first-party verification.

A `weak` verified event can still be commercially important. It simply means the market-validation work has not been done yet.

## Repository layout

```text
config/sources.yml          first-party source registry
src/gapradar/detector.py    feed parsing, hard-event detection, domain guardrails
src/gapradar/models.py      evidence/event model
src/gapradar/store.py       persistent event store
src/gapradar/cli.py         scan / doctor / report / export commands
src/gapradar/render.py      static radar dashboard
data/events.json            verified event state
data/source-health.json     latest source-health snapshot
docs/index.html             generated dashboard
.github/workflows/          CI + daily live radar
tests/                      detector and evidence guardrail tests
```

## Guardrails

1. **No official source, no verified event.**
2. Reddit, HN, GitHub issues, social posts, and directories can never become Tier 1 evidence.
3. A GitHub repository being archived is not by itself proof of displaced demand.
4. Detection and commercial evaluation are separate stages.
5. One failing source must not stop the rest of the radar.
6. Incidental words such as “deprecated” in an unrelated announcement must not create an event.
7. Silence is a valid result.

## Roadmap

**V0.1 — Hard-event skeleton**  
Evidence model, initial classifier, persistence, CLI, scheduled scan, CI.

**V0.2 — Precision-first live radar** ✅  
Real first-party feeds, source health, bounded lookback, live GitHub Action runs, false-positive regression tests, generated dashboard.

**V0.3 — Displaced-demand validation**  
Attach recent reaction evidence, deduplicate reactions, distinguish forced migration pain from ordinary discussion, and keep provenance for every reaction.

**V0.4 — Supply-gap analysis**  
Map existing substitutes and determine whether displaced demand is already well served.

**V0.5 — Opportunity dossier**  
Produce a fully cited human-review dossier: what changed, who appears displaced, what substitutes exist, what remains unsolved, and why the gap may or may not be worth building for.

## License

MIT © 2026 Amazing Kimi

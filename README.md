# GapRadar

**Detect verified market changes before they become obvious opportunities.**

GapRadar watches first-party sources for software shutdowns, end-of-life notices, pricing shocks, API deprecations, and major policy changes. It separates **facts** from **market reaction** and **replacement supply** so a real-world event is never mistaken for a business opportunity without evidence.

> Market changes create displaced demand. GapRadar is the radar, not the hype machine.

## Why

Most startup-idea tools begin with complaints and ask an AI to invent an opportunity. GapRadar starts somewhere stricter: a **timestamped, verifiable market event**.

The core pipeline is:

```text
DETECT → VERIFY → REACTION → SUPPLY → POTENTIAL GAP
```

V0.1 deliberately stops early. It detects and verifies hard events first. Community chatter and alternative directories can strengthen a signal later, but they can never verify the event itself.

## V0.1 scope

GapRadar currently recognizes three event families:

- **Shutdown / EOL** — product retirement, shutdown, discontinuation, end-of-life.
- **Price Shock** — material pricing changes, especially free-tier removal or major price increases.
- **API / Terms Change** — API deprecation, sunset, breaking platform-policy or terms changes.

### Evidence hierarchy

| Tier | Purpose | Examples | Can verify an event? |
| --- | --- | --- | --- |
| Tier 1 — Official | Establish the fact | vendor changelog, official blog, developer docs | **Yes** |
| Tier 2 — Reaction | Measure displaced demand | forums, HN, Reddit, GitHub issues | No |
| Tier 3 — Supply | Measure replacement quality | directories, app stores, competing products | No |

An event with no first-party source remains `insufficient_evidence` by design.

## Confidence is not an opportunity score

GapRadar does **not** emit fake precision such as `91/100 opportunity` or an invented `3–6 month window`.

Current confidence labels are evidence labels only:

- `weak` — official event verified, little downstream evidence yet.
- `emerging` — official event + at least one reaction signal.
- `strong` — official event + repeated reaction + replacement/supply evidence.
- `insufficient_evidence` — no qualifying first-party verification.

These labels describe the **evidence chain**, not guaranteed commercial value.

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
gapradar scan
gapradar report
```

Configured first-party feeds live in [`config/sources.yml`](config/sources.yml). Scan results are stored in `data/events.json`.

## Automated radar

The repository includes a scheduled GitHub Actions workflow that runs the scanner daily. New verified events are committed back to `data/events.json`; if nothing changes, it commits nothing.

The source registry is intentionally small in V0.1. The goal is signal quality before coverage.

## Guardrails

1. **No official source, no verified event.**
2. A Reddit post, HN thread, GitHub issue, or directory listing can never become Tier 1 evidence.
3. A GitHub repository being archived is not, by itself, proof of displaced demand.
4. Detection and commercial evaluation are separate stages.
5. One failing source must not stop the rest of the radar.
6. The project prefers an honest `insufficient_evidence` over a confident guess.

## Current architecture

```text
config/sources.yml
        ↓
official feed scanner
        ↓
keyword/event classifier
        ↓
official-domain verification
        ↓
MarketEvent model
        ↓
data/events.json
        ↓
CLI report
```

The data model already has separate slots for Tier 2 reaction evidence and Tier 3 supply evidence so later versions can add demand validation without weakening the Tier 1 rule.

## Roadmap

**V0.1 — Hard-event radar**  
Official-source detection, verification, persistence, evidence model, tests, scheduled scan.

**V0.2 — Displaced-demand validation**  
Attach recent reaction evidence, deduplicate reactions, distinguish migration pain from ordinary discussion.

**V0.3 — Supply-gap analysis**  
Map existing substitutes and determine whether the displaced demand is already well served.

**V0.4 — Opportunity dossier**  
Produce a fully cited human-review dossier: what changed, who appears displaced, what substitutes exist, what remains unsolved, and why the gap may or may not be worth building for.

## License

MIT © 2026 Amazing Kimi

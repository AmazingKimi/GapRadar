# GapRadar

**GapRadar watches what changes in the world, verifies which changes are real, then investigates where they may create demand the market has not adequately served.**

It does **not** start from complaints. Community reaction is supporting evidence only.

## Product model

```text
WORLD SCAN
broad + noisy discovery
        ↓
CANDIDATE EVENT
not yet a fact
        ↓
VERIFY
Tier-1 / first-party confirmation
        ↓
DEMAND HYPOTHESIS
explicit, reviewable, allowed to be low-confidence
        ↓
   ┌───────────────┐
   ↓               ↓
REACTION         SUPPLY
confidence       market coverage
modifier         assessment
   └───────┬───────┘
           ↓
      GAP JUDGMENT
           ↓
        DOSSIER
```

The discovery layer is intentionally broad and noisy. The verification layer remains precision-first. A confidently detected event can still be a bad opportunity.

## Core architecture rule

**Reaction evidence adjusts confidence; it never decides whether a verified demand hypothesis may exist and it never blocks supply analysis.**

A verified shutdown, price shock, API/platform change, or similar structural event can therefore stay alive as a low-confidence market hypothesis even when Hacker News, GitHub Issues, Reddit, or a vendor community shows no qualifying reaction.

## Demand hypothesis

Every verified event now records an explicit `DemandHypothesis` instead of jumping directly from “change happened” to “market gap exists”. It contains:

- affected users;
- job to be done;
- disruption created by the change;
- official successor / migration path when known;
- evidence basis;
- confidence: `low`, `medium`, or `high`;
- unresolved unknowns.

The hypothesis is allowed to be wrong. Its purpose is to make the inference visible and falsifiable rather than hiding it inside a score or LLM narrative.

Reaction evidence can raise hypothesis confidence:

- no qualifying reaction / failed search → hypothesis remains `low`;
- early reaction signal → `medium`;
- repeated reaction signal → `high`.

Missing reaction never means “no demand”.

## Supply analysis

Supply now runs for any **verified event with an explicit demand hypothesis**. It no longer waits for the event to “survive” a reaction gate.

Current supply states:

- `unassessed`
- `no_supply`
- `thin_supply`
- `served`

Current gap states:

- `unassessed`
- `watch`
- `potential_gap`
- `likely_served`

Interpretation:

- verified hypothesis + supply unassessed → no gap verdict yet;
- verified hypothesis + thin/no supply + weak/no reaction → `watch`;
- verified hypothesis + repeated reaction + thin/no supply → `potential_gap`;
- strong replacement supply → `likely_served` even when reaction is absent.

## Daily signal funnel

The dashboard now exposes a funnel instead of forcing a daily winner count:

```text
world-scan candidates
        ↓
Tier-1 verified events
        ↓
explicit demand hypotheses
        ↓
supply maps completed
        ↓
WATCH / REVIEW / LIKELY SERVED
```

A day with zero market gaps can be a correct result. The funnel is a health signal, not a quota.

## Discovery vs verification

These are deliberately separate responsibilities:

- `worldscan.py` — broad candidate discovery from news and industry feeds; noisy by design.
- `detector.py` — precision-first hard-event verification and official-domain guardrails.

Do not weaken `detector.py` just to make the broad scanner produce more candidates.

Current broad discovery includes targeted Google News feeds plus selected technology/industry feeds. Current first-party verification sources include GitHub, Shopify, Slack and Cloudflare.

## Evidence hierarchy

| Tier | Purpose | Examples | Can verify the event? |
| --- | --- | --- | --- |
| Tier 1 — Official | Establish the fact | vendor changelog, official blog, developer docs | **Yes** |
| Tier 2 — Reaction | Adjust demand confidence | HN, GitHub Issues, forums, vendor communities | No |
| Tier 3 — Supply | Assess whether the job is already served | GitHub repositories, npm, competing products | No |

**No Tier-1 source = no verified event.** Tier-2 and Tier-3 evidence may evaluate a verified event, but neither can manufacture a Tier-1 fact.

## Current verification benchmark

The V0.7 historical fixture benchmark remains useful, but its meaning is deliberately narrow.

Observed in GitHub Actions run `34312896873` on 2026-09-09:

| Metric | Fixture replay | Wayback replay |
| --- | ---: | ---: |
| Cases total | 24 | 24 |
| Cases actually evaluated | 24 | 2 |
| TP / FP / TN / FN | 17 / 1 / 5 / 1 | 2 / 0 / 0 / 0 |
| Precision | 0.9444 | 1.0000* |
| Recall | 0.9444 | 1.0000* |
| Event-type accuracy | 0.9412 | 1.0000* |
| Archive coverage | 1.0000 | 0.0833 |

\* Wayback precision/recall is not meaningful evidence because only 2 of 24 official cases were retrievable in that run.

This benchmark primarily measures **classification / verification logic when the historical evidence item is already present**. It must not be presented as proof that WORLD SCAN can discover 94.44% of real market changes from an open information stream.

Known fixture failures remain visible:

- false negative: IFTTT SMS/Phone free-access change;
- false positive: normal IFTTT Pro guide misclassified as price shock;
- type mismatch: Chrome Manifest V2 classified as shutdown/EOL instead of API/platform change.

## Current live boundary

Broad discovery: targeted Google News searches plus selected tech / industry RSS feeds.  
First-party verification: GitHub, Shopify, Slack, Cloudflare.  
Reaction support: Hacker News and GitHub Issues, with ecosystem routing metadata for missing vendor-community coverage.  
Supply: GitHub repositories and npm.

This is **not an all-web radar**. Coverage is still narrow and candidate false positives remain an active engineering problem.

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest

gapradar world-scan
gapradar doctor
gapradar scan
gapradar validate-demand
gapradar validate-supply
gapradar build-dossiers
gapradar export
python -m http.server 8000 --directory docs
```

Then open `http://localhost:8000`.

The Daily Radar workflow runs the same chain automatically and commits refreshed world candidates, verified events, demand hypotheses, evidence, dossiers and dashboard output.

## Guardrails

1. **No official source, no verified event.**
2. WORLD SCAN candidates are leads, not facts.
3. Discovery confidence and opportunity confidence are separate.
4. Every verified event must expose an explicit demand hypothesis before a market-gap judgment.
5. Demand hypotheses may be low-confidence; uncertainty must be visible.
6. Reaction evidence adjusts confidence; it never gates hypothesis creation or supply analysis.
7. A failed reaction search cannot become `no_signal`.
8. `no_signal` means “not detected by these queries”, never “no demand exists”.
9. Popular software is not replacement supply unless it is relevant to the affected job.
10. Strong replacement supply can mark a hypothesis `likely_served` even when reaction evidence is absent.
11. `REVIEW` requires stronger evidence than `WATCH`; missing evidence is never silently invented.
12. Dossiers do not fabricate market size, revenue forecasts, opportunity scores, or build windows.
13. Archive failure is archive failure, not detector failure.
14. Fixture accuracy is benchmark accuracy, not market-wide discovery accuracy.
15. Historical recall rules may not silently weaken live precision.

## Repository layout

```text
config/world_sources.yml       broad world/news discovery sources
config/sources.yml             first-party verification sources
src/gapradar/worldscan.py      broad candidate discovery
src/gapradar/detector.py       precision-first event verification
src/gapradar/models.py         demand hypothesis + evidence + state machine
src/gapradar/reaction.py       supporting reaction search
src/gapradar/supply.py         replacement-supply search, independent of reaction
src/gapradar/dossier.py        hypothesis-first opportunity dossier
src/gapradar/backtest.py       historical verification replay
src/gapradar/render.py         Today’s Market Gaps dashboard + signal funnel
src/gapradar/cli.py            radar commands
data/world-gaps.json           broad candidate state
data/events.json               verified event state + hypotheses + evidence
data/dossiers.json             generated dossier index
docs/index.html                standalone dashboard
.github/workflows/radar.yml    automated daily discovery/verification pipeline
tests/                         regression and evidence-state tests
```

## Roadmap

**V0.1 — Hard-event skeleton** ✅  
**V0.2 — Precision-first live radar** ✅  
**V0.3 — Reaction evidence** ✅  
**V0.4 — Supply analysis** ✅  
**V0.5 — Opportunity dossier** ✅  
**V0.6 — Auditable evidence search** ✅  
**V0.7 — Historical verification benchmark** ✅  
**V0.8 — World-change discovery + explicit demand hypotheses** 🚧

The next benchmark should test the discovery layer itself: give GapRadar a noisy historical information stream without preselecting the event URL and measure whether WORLD SCAN retrieves the known structural events without flooding the pipeline with false positives.

## License

MIT © 2026 Amazing Kimi

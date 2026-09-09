from __future__ import annotations

from dataclasses import dataclass

from .models import MarketEvent


@dataclass(frozen=True)
class ReactionSourcePlan:
    ecosystem: str
    preferred_sources: tuple[str, ...]
    implemented_sources: tuple[str, ...]

    @property
    def missing_sources(self) -> tuple[str, ...]:
        return tuple(source for source in self.preferred_sources if source not in self.implemented_sources)


# This is deliberately a routing/coverage map, not a claim that the missing source
# is already searchable. Missing preferred sources are surfaced in dossiers and
# downgrade search coverage instead of being silently ignored.
_VENDOR_PLANS: dict[str, ReactionSourcePlan] = {
    "shopify": ReactionSourcePlan(
        ecosystem="commerce_platform",
        preferred_sources=("shopify_community", "github_issues", "hacker_news"),
        implemented_sources=("github_issues", "hacker_news"),
    ),
    "slack": ReactionSourcePlan(
        ecosystem="developer_platform",
        preferred_sources=("slack_community", "github_issues", "hacker_news"),
        implemented_sources=("github_issues", "hacker_news"),
    ),
    "cloudflare": ReactionSourcePlan(
        ecosystem="infra_platform",
        preferred_sources=("cloudflare_community", "github_issues", "hacker_news"),
        implemented_sources=("github_issues", "hacker_news"),
    ),
}

_DEFAULT_PLAN = ReactionSourcePlan(
    ecosystem="developer_general",
    preferred_sources=("github_issues", "hacker_news"),
    implemented_sources=("github_issues", "hacker_news"),
)


def reaction_source_plan(event: MarketEvent) -> ReactionSourcePlan:
    vendor = event.vendor.strip().lower()
    for key, plan in _VENDOR_PLANS.items():
        if key in vendor:
            return plan
    return _DEFAULT_PLAN


def reaction_coverage(event: MarketEvent) -> dict[str, object]:
    plan = reaction_source_plan(event)
    checked = set(event.reaction_sources_checked)
    preferred = list(plan.preferred_sources)
    missing = [source for source in preferred if source not in checked]
    return {
        "ecosystem": plan.ecosystem,
        "preferred_sources": preferred,
        "implemented_sources": list(plan.implemented_sources),
        "checked_sources": list(event.reaction_sources_checked),
        "missing_sources": missing,
        "coverage_complete": not missing,
    }

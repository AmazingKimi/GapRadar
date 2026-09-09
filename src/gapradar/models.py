from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


class EventType(str, Enum):
    SHUTDOWN = "shutdown_eol"
    PRICE_SHOCK = "price_shock"
    API_TERMS = "api_terms_change"


class EvidenceTier(str, Enum):
    TIER_1_OFFICIAL = "tier_1_official"
    TIER_2_REACTION = "tier_2_reaction"
    TIER_3_SUPPLY = "tier_3_supply"


class Confidence(str, Enum):
    STRONG = "strong"
    EMERGING = "emerging"
    WEAK = "weak"
    INSUFFICIENT = "insufficient_evidence"


class DemandHypothesis(BaseModel):
    affected_users: str
    job_to_be_done: str
    disruption: str
    official_successor: str = "unknown"
    basis: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "low"
    unknowns: list[str] = Field(default_factory=list)


class SourceEvidence(BaseModel):
    tier: EvidenceTier
    title: str
    url: HttpUrl
    publisher: str
    published_at: datetime | None = None
    excerpt: str = ""
    is_official: bool = False
    source_kind: str | None = None
    signal: Literal["migration_pain", "replacement_supply", "discussion", "unknown"] | None = None
    signal_score: int = 0
    engagement: int = 0


class MarketEvent(BaseModel):
    id: str
    product: str
    vendor: str
    event_type: EventType
    headline: str
    summary: str
    event_date: datetime | None = None
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    official_evidence: list[SourceEvidence] = Field(default_factory=list)
    demand_hypothesis: DemandHypothesis | None = None
    reaction_evidence: list[SourceEvidence] = Field(default_factory=list)
    supply_evidence: list[SourceEvidence] = Field(default_factory=list)
    reaction_checked_at: datetime | None = None
    reaction_sources_checked: list[str] = Field(default_factory=list)
    reaction_candidate_count: int = 0
    reaction_queries: list[dict[str, object]] = Field(default_factory=list)
    reaction_search_quality: Literal["unassessed", "adequate", "degraded", "failed"] = "unassessed"
    demand_status: Literal["unassessed", "no_signal", "early_signal", "repeated_signal"] = "unassessed"
    supply_checked_at: datetime | None = None
    supply_sources_checked: list[str] = Field(default_factory=list)
    supply_candidate_count: int = 0
    supply_status: Literal["unassessed", "no_supply", "thin_supply", "served"] = "unassessed"
    gap_status: Literal["unassessed", "no_demand", "watch", "potential_gap", "likely_served"] = "unassessed"
    confidence: Confidence = Confidence.INSUFFICIENT
    status: Literal["candidate", "verified", "rejected"] = "candidate"
    notes: list[str] = Field(default_factory=list)

    @field_validator("official_evidence")
    @classmethod
    def official_evidence_must_be_tier_1(cls, items: list[SourceEvidence]) -> list[SourceEvidence]:
        for item in items:
            if item.tier != EvidenceTier.TIER_1_OFFICIAL or not item.is_official:
                raise ValueError("official_evidence must contain only verified tier-1 official sources")
        return items

    @field_validator("reaction_evidence")
    @classmethod
    def reaction_evidence_must_be_tier_2(cls, items: list[SourceEvidence]) -> list[SourceEvidence]:
        for item in items:
            if item.tier != EvidenceTier.TIER_2_REACTION or item.is_official:
                raise ValueError("reaction_evidence must contain only non-official tier-2 sources")
        return items

    @field_validator("supply_evidence")
    @classmethod
    def supply_evidence_must_be_tier_3(cls, items: list[SourceEvidence]) -> list[SourceEvidence]:
        for item in items:
            if item.tier != EvidenceTier.TIER_3_SUPPLY or item.is_official:
                raise ValueError("supply_evidence must contain only non-official tier-3 sources")
        return items

    def _ensure_demand_hypothesis(self) -> None:
        if self.demand_hypothesis is not None or not self.official_evidence:
            return
        basis = [f"{item.publisher}: {item.title}" for item in self.official_evidence[:3]]
        if self.event_type == EventType.SHUTDOWN:
            hypothesis = DemandHypothesis(
                affected_users=f"Users and organizations still relying on {self.product}.",
                job_to_be_done=f"Continue the workflow currently handled by {self.product} after the incumbent removes it.",
                disruption="The incumbent is ending or removing a product, workflow, or supported capability.",
                basis=basis,
                unknowns=["Actual active user count", "Migration urgency by segment", "Quality of official successor or migration path"],
            )
        elif self.event_type == EventType.PRICE_SHOCK:
            hypothesis = DemandHypothesis(
                affected_users=f"Price-sensitive customers currently paying for {self.product}.",
                job_to_be_done=f"Preserve the core outcome of {self.product} at a more acceptable cost or pricing model.",
                disruption="A material pricing change may make the incumbent uneconomic for part of its customer base.",
                basis=basis,
                unknowns=["Share of customers affected", "Switching costs", "Whether cheaper substitutes already satisfy the core job"],
            )
        else:
            hypothesis = DemandHypothesis(
                affected_users=f"Developers and businesses dependent on {self.product} or its platform/API behavior.",
                job_to_be_done="Keep integrations and dependent workflows functioning after the platform change.",
                disruption="An API, terms, licensing, or platform-policy change may force rewrites, migration, or dependency replacement.",
                basis=basis,
                unknowns=["Number of affected integrations", "Migration complexity", "Availability of compatible alternatives"],
            )
        self.demand_hypothesis = hypothesis

    def verify(self) -> "MarketEvent":
        if not self.official_evidence:
            self.status = "candidate"
            self.confidence = Confidence.INSUFFICIENT
            self.gap_status = "unassessed"
            if "No official first-party evidence." not in self.notes:
                self.notes.append("No official first-party evidence.")
            return self

        self.status = "verified"
        self._ensure_demand_hypothesis()
        reaction_count = len(self.reaction_evidence)
        supply_count = len(self.supply_evidence)

        if self.reaction_checked_at is None or self.reaction_search_quality in {"unassessed", "failed"}:
            self.demand_status = "unassessed"
        elif reaction_count >= 3:
            self.demand_status = "repeated_signal"
        elif reaction_count >= 1:
            self.demand_status = "early_signal"
        else:
            self.demand_status = "no_signal"

        if self.demand_hypothesis is not None:
            if self.demand_status == "repeated_signal":
                self.demand_hypothesis.confidence = "high"
            elif self.demand_status == "early_signal":
                self.demand_hypothesis.confidence = "medium"
            else:
                self.demand_hypothesis.confidence = "low"

        if self.supply_checked_at is None:
            self.supply_status = "unassessed"
        elif supply_count >= 3 or any(item.signal_score >= 7 for item in self.supply_evidence):
            self.supply_status = "served"
        elif supply_count >= 1:
            self.supply_status = "thin_supply"
        else:
            self.supply_status = "no_supply"

        # Reaction is a confidence modifier, never a gate. Once an event is verified
        # and has a demand hypothesis, supply can be assessed even with no reaction.
        if self.demand_hypothesis is None or self.supply_status == "unassessed":
            self.gap_status = "unassessed"
        elif self.supply_status == "served":
            self.gap_status = "likely_served"
        elif self.supply_status in {"no_supply", "thin_supply"} and self.demand_status == "repeated_signal":
            self.gap_status = "potential_gap"
        elif self.supply_status in {"no_supply", "thin_supply"}:
            self.gap_status = "watch"
        else:
            self.gap_status = "watch"

        if self.gap_status == "potential_gap":
            self.confidence = Confidence.STRONG
        elif self.gap_status in {"watch", "likely_served"} or reaction_count >= 1:
            self.confidence = Confidence.EMERGING
        else:
            self.confidence = Confidence.WEAK
        return self

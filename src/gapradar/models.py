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

    def verify(self) -> "MarketEvent":
        if not self.official_evidence:
            self.status = "candidate"
            self.confidence = Confidence.INSUFFICIENT
            self.gap_status = "unassessed"
            if "No official first-party evidence." not in self.notes:
                self.notes.append("No official first-party evidence.")
            return self

        self.status = "verified"
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

        if self.supply_checked_at is None:
            self.supply_status = "unassessed"
        elif supply_count >= 3 or any(item.signal_score >= 7 for item in self.supply_evidence):
            self.supply_status = "served"
        elif supply_count >= 1:
            self.supply_status = "thin_supply"
        else:
            self.supply_status = "no_supply"

        if self.demand_status == "no_signal":
            self.gap_status = "no_demand"
        elif self.demand_status == "unassessed" or self.supply_status == "unassessed":
            self.gap_status = "unassessed"
        elif self.supply_status == "served":
            self.gap_status = "likely_served"
        elif self.demand_status == "repeated_signal" and self.supply_status in {"no_supply", "thin_supply"}:
            self.gap_status = "potential_gap"
        elif self.demand_status == "early_signal" and self.supply_status in {"no_supply", "thin_supply"}:
            self.gap_status = "watch"
        else:
            self.gap_status = "watch"

        if self.gap_status == "potential_gap":
            self.confidence = Confidence.STRONG
        elif reaction_count >= 1:
            self.confidence = Confidence.EMERGING
        else:
            self.confidence = Confidence.WEAK
        return self

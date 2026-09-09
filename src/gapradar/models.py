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

    def verify(self) -> "MarketEvent":
        if not self.official_evidence:
            self.status = "candidate"
            self.confidence = Confidence.INSUFFICIENT
            if "No official first-party evidence." not in self.notes:
                self.notes.append("No official first-party evidence.")
            return self

        self.status = "verified"
        reaction_count = len(self.reaction_evidence)
        supply_count = len(self.supply_evidence)

        if reaction_count >= 3 and supply_count >= 1:
            self.confidence = Confidence.STRONG
        elif reaction_count >= 1:
            self.confidence = Confidence.EMERGING
        else:
            self.confidence = Confidence.WEAK
        return self

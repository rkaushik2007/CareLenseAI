"""Pydantic models for API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Grain = Literal["state", "district", "pin"]
Verdict = Literal["desert", "blind", "served", "unknown"]
SortKey = Literal["priority", "risk", "conf", "az"]


class CapabilityOut(BaseModel):
    id: str
    label: str
    dot: str
    coverage: float


class SummaryOut(BaseModel):
    desert: int
    blind: int
    served: int
    unknown: int


class UnitOut(BaseModel):
    unit_key: str
    name: str
    sub: str
    risk: int
    conf: int
    verdict: Verdict
    watched: bool = False
    hasNote: bool = False
    n_facilities: int = 0
    priority: float = 0.0


class NeedDriver(BaseModel):
    label: str
    value: float | None = None
    direction: str


class EvidenceItem(BaseModel):
    facility: str
    quote: str
    tier: str
    source_field: str
    rec_id: str
    source_url: str | None = None
    source: str = ""


class UnitDetailOut(BaseModel):
    unit_key: str
    name: str
    sub: str
    risk: int
    conf: int
    verdict: Verdict
    base_verdict: Verdict
    overridden: bool = False
    supply: dict[str, Any]
    need: dict[str, Any]
    evidence: list[EvidenceItem]
    note: str = ""
    watched: bool = False


class GeoFeatureOut(BaseModel):
    unit_key: str
    state: str
    district: str | None = None
    pin3: str | None = None
    risk: int
    conf: int
    verdict: Verdict


class WatchRequest(BaseModel):
    unit_key: str
    cap: str
    on: bool


class NoteRequest(BaseModel):
    unit_key: str
    cap: str
    note: str


class OverrideRequest(BaseModel):
    unit_key: str
    cap: str
    verdict: Verdict | None = None


class ScenarioIn(BaseModel):
    name: str
    cap: str
    grain: Grain
    overlay: bool = False
    sort: SortKey = "priority"


class AskRequest(BaseModel):
    question: str


class VerificationPlanRequest(BaseModel):
    unit_keys: list[str] = Field(default_factory=list)
    cap: str = "icu"

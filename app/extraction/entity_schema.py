from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    COMPONENT = "component"
    INTERFACE = "interface"
    PORT = "port"
    SIGNAL = "signal"
    DEPENDENCY = "dependency"
    FUNCTIONAL_FLOW = "functional_flow"


class EntityEvidence(BaseModel):
    document_id: str
    document_version: str
    page_number: int
    section: str
    source_text: str = Field(min_length=1)


class ArchitectureEntityRecord(BaseModel):
    entity_id: str
    entity_type: EntityType
    name: str = Field(min_length=1)
    description: str = ""
    confidence: float = Field(ge=0.0, le=1.0)

    document_id: str
    document_version: str

    evidence: list[EntityEvidence] = Field(default_factory=list)

    attributes: dict[str, str] = Field(default_factory=dict)


class ArchitectureRelationshipRecord(BaseModel):
    relationship_id: str
    relationship_type: str

    source_entity_id: str
    target_entity_id: str

    document_id: str
    document_version: str

    confidence: float = Field(ge=0.0, le=1.0)

    evidence: list[EntityEvidence] = Field(default_factory=list)

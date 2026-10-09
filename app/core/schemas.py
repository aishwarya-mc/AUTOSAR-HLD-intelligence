from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    healthy = "healthy"
    degraded = "degraded"


class HealthResponse(BaseModel):
    status: HealthStatus
    service: str
    version: str


class DocumentStatus(str, Enum):
    uploaded = "uploaded"
    processing = "processing"
    processed = "processed"
    failed = "failed"


class DocumentMetadata(BaseModel):
    document_id: str
    filename: str
    version: str
    file_type: str
    file_size_bytes: int
    page_count: int | None = None
    status: DocumentStatus = DocumentStatus.uploaded
    created_at: datetime


class SourceEvidence(BaseModel):
    document_id: str
    document_version: str
    page_number: int | None = None
    section: str | None = None
    chunk_id: str | None = None
    excerpt: str | None = None


class ArchitectureEntity(BaseModel):
    entity_id: str
    entity_type: str
    name: str
    description: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[SourceEvidence] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class ArchitectureRelationship(BaseModel):
    relationship_id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[SourceEvidence] = Field(default_factory=list)


class QueryRequest(BaseModel):
    question: str = Field(min_length=3)
    document_id: str | None = None
    version: str | None = None
    top_k: int = Field(default=8, ge=1, le=50)


class Citation(BaseModel):
    citation_id: str
    page_number: int | None = None
    section: str | None = None
    document_id: str
    document_version: str
    excerpt: str | None = None


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    grounded: bool = False
    limitations: list[str] = Field(default_factory=list)
    generated_by: str | None = None  # e.g. 'ollama:llama3.2' when an LLM phrased the answer


class FindingSeverity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class ValidationFinding(BaseModel):
    finding_id: str
    rule_id: str
    title: str
    description: str
    severity: FindingSeverity
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[SourceEvidence] = Field(default_factory=list)


class ReviewStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    needs_review = "needs_review"


class ReviewAction(BaseModel):
    finding_id: str
    status: ReviewStatus
    reviewer: str
    comment: str | None = None

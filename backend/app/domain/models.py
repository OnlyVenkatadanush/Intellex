from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field

class UserDomain(BaseModel):
    id: str
    email: EmailStr
    password_hash: Optional[str] = None
    google_oauth_id: Optional[str] = None
    role: str = "Researcher"
    created_at: datetime

class SessionDomain(BaseModel):
    id: str
    user_id: str
    original_query: str
    status: str = "PENDING"
    report_markdown: Optional[str] = None
    created_at: datetime

class CitationDomain(BaseModel):
    id: str
    finding_id: str
    source_title: str
    source_url: Optional[str] = None
    citation_format: str = "APA"
    quote: Optional[str] = None
    authors: Optional[List[str]] = None
    year: Optional[str] = None
    journal: Optional[str] = None
    doi: Optional[str] = None
    source_type: Optional[str] = None
    created_at: datetime

class FindingDomain(BaseModel):
    id: str
    session_id: str
    claim: str
    confidence_score: float = 0.0
    source_count: int = 0
    source_quality_score: float = 0.0
    verification_status: str = "INSUFFICIENT_EVIDENCE" # VERIFIED, PARTIALLY_VERIFIED, CONFLICTING_EVIDENCE, INSUFFICIENT_EVIDENCE, UNVERIFIED
    consensus_rationale: Optional[str] = None
    supporting_sources: Optional[List[str]] = []
    contradicting_sources: Optional[List[str]] = []
    credibility_score: float = 0.0
    reasoning_trace: Optional[str] = None
    evidence_strength: float = 0.0
    cross_source_agreement: float = 0.0
    recency_score: float = 0.0
    contradiction_penalty: float = 0.0
    citations: List[CitationDomain] = []
    created_at: datetime

class DocumentDomain(BaseModel):
    id: str
    session_id: str
    filename: str
    file_type: str
    extracted_text: str
    created_at: datetime

class MemoryDomain(BaseModel):
    id: str
    user_id: str
    content: str
    embedding: Optional[List[float]] = None
    created_at: datetime

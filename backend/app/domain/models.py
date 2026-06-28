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
    created_at: datetime

class FindingDomain(BaseModel):
    id: str
    session_id: str
    claim: str
    confidence_score: float = 0.0
    source_count: int = 0
    source_quality_score: float = 0.0
    verification_status: str = "INSUFFICIENT_EVIDENCE" # VERIFIED, CONTRADICTED, INSUFFICIENT_EVIDENCE
    consensus_rationale: Optional[str] = None
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

from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Any
from datetime import datetime

# --- Token Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None

# --- User Schemas ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: Optional[str] = "Researcher"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

# --- Log Schemas ---
class ExecutionLogResponse(BaseModel):
    id: str
    session_id: str
    agent_name: str
    agent_role: str
    message: str
    log_type: str
    created_at: datetime

    class Config:
        from_attributes = True

# --- Citation Schemas ---
class CitationCreate(BaseModel):
    source_title: str
    source_url: Optional[str] = None
    citation_format: Optional[str] = "APA"
    quote: Optional[str] = None

class CitationResponse(BaseModel):
    id: str
    source_title: str
    source_url: Optional[str] = None
    citation_format: str
    quote: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# --- Finding Schemas ---
class FindingResponse(BaseModel):
    id: str
    claim: str
    confidence_score: float
    source_count: int
    source_quality_score: float
    verification_status: str
    consensus_rationale: Optional[str] = None
    citations: List[CitationResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True

# --- Session Schemas ---
class SessionCreate(BaseModel):
    original_query: str

class SessionResponse(BaseModel):
    id: str
    original_query: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class SessionDetailResponse(BaseModel):
    id: str
    original_query: str
    status: str
    report_markdown: Optional[str] = None
    created_at: datetime
    findings: List[FindingResponse] = []
    logs: List[ExecutionLogResponse] = []

    class Config:
        from_attributes = True

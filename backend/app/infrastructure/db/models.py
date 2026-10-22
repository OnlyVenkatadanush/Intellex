import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Numeric, Integer, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.database import Base

class DBUser(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=True)
    google_oauth_id = Column(String, nullable=True)
    role = Column(String, nullable=False, default="Researcher")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sessions = relationship("DBSession", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("DBMemory", back_populates="user", cascade="all, delete-orphan")


class DBSession(Base):
    __tablename__ = "research_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    original_query = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="PENDING")  # PENDING, PLANNING, RESEARCHING, DEBATING, COMPLETED, FAILED
    report_markdown = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("DBUser", back_populates="sessions")
    findings = relationship("DBFinding", back_populates="session", cascade="all, delete-orphan")
    documents = relationship("DBDocument", back_populates="session", cascade="all, delete-orphan")
    logs = relationship("DBExecutionLog", back_populates="session", cascade="all, delete-orphan")
    debates = relationship("DBDebate", back_populates="session", cascade="all, delete-orphan")


class DBFinding(Base):
    __tablename__ = "findings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False)
    claim = Column(Text, nullable=False)
    confidence_score = Column(Numeric(5, 2), nullable=False, default=0.0)
    source_count = Column(Integer, nullable=False, default=0)
    source_quality_score = Column(Numeric(4, 2), nullable=False, default=0.0)
    verification_status = Column(String(50), nullable=False, default="INSUFFICIENT_EVIDENCE") # VERIFIED, PARTIALLY_VERIFIED, CONFLICTING_EVIDENCE, INSUFFICIENT_EVIDENCE, UNVERIFIED
    consensus_rationale = Column(Text, nullable=True)
    
    # Research Integrity & Scoring Engine updates
    supporting_sources = Column(JSON, nullable=True)     # JSON array of source identifiers
    contradicting_sources = Column(JSON, nullable=True)   # JSON array of source identifiers
    credibility_score = Column(Numeric(5, 2), nullable=False, default=0.0)
    reasoning_trace = Column(Text, nullable=True)
    evidence_strength = Column(Numeric(5, 2), nullable=False, default=0.0)
    cross_source_agreement = Column(Numeric(5, 2), nullable=False, default=0.0)
    recency_score = Column(Numeric(5, 2), nullable=False, default=0.0)
    contradiction_penalty = Column(Numeric(5, 2), nullable=False, default=0.0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("DBSession", back_populates="findings")
    citations = relationship("DBCitation", back_populates="finding", cascade="all, delete-orphan")


class DBCitation(Base):
    __tablename__ = "citations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    finding_id = Column(String, ForeignKey("findings.id", ondelete="CASCADE"), nullable=False)
    source_title = Column(Text, nullable=False)
    source_url = Column(Text, nullable=True)
    citation_format = Column(String(20), nullable=False, default="APA") # APA, IEEE
    quote = Column(Text, nullable=True)
    
    # Metadata fields for real citations
    authors = Column(JSON, nullable=True)                # JSON serialized array of strings
    year = Column(String(50), nullable=True)
    journal = Column(String(255), nullable=True)
    doi = Column(String(255), nullable=True)
    source_type = Column(String(100), nullable=True)     # PubMed, arXiv, Crossref, Tavily, etc.

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    finding = relationship("DBFinding", back_populates="citations")


class DBDocument(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False) # PDF, DOCX, TXT, CSV, IMAGE
    extracted_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("DBSession", back_populates="documents")


class DBMemory(Base):
    __tablename__ = "memories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)  # Store embedding floats list. In PostgreSQL with pgvector, vector datatype is loaded.
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("DBUser", back_populates="memories")


class DBExecutionLog(Base):
    __tablename__ = "execution_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False)
    agent_name = Column(String(100), nullable=False)
    agent_role = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    log_type = Column(String(50), nullable=False)  # INFO, WARNING, ERROR, PROGRESS
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("DBSession", back_populates="logs")


class DBDebate(Base):
    __tablename__ = "debates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False)
    source_a_claim = Column(Text, nullable=False)
    source_b_claim = Column(Text, nullable=False)
    conflict_explanation = Column(Text, nullable=False)
    evidence_comparison = Column(Text, nullable=False)
    final_resolution = Column(Text, nullable=False)
    resolution_confidence = Column(Numeric(5, 2), nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("DBSession", back_populates="debates")

from typing import List, Optional
from sqlalchemy.orm import Session
from backend.app.application.repositories import (
    UserRepository, SessionRepository, FindingRepository, CitationRepository, DocumentRepository, MemoryRepository
)
from backend.app.domain.models import (
    UserDomain, SessionDomain, FindingDomain, CitationDomain, DocumentDomain, MemoryDomain
)
from backend.app.infrastructure.db.models import (
    DBUser, DBSession, DBFinding, DBCitation, DBDocument, DBMemory
)

class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, db: Session):
        self.db = db

    def _to_domain(self, db_user: DBUser) -> UserDomain:
        return UserDomain(
            id=db_user.id,
            email=db_user.email,
            password_hash=db_user.password_hash,
            google_oauth_id=db_user.google_oauth_id,
            role=db_user.role,
            created_at=db_user.created_at
        )

    async def get_by_id(self, user_id: str) -> Optional[UserDomain]:
        db_user = self.db.query(DBUser).filter(DBUser.id == user_id).first()
        return self._to_domain(db_user) if db_user else None

    async def get_by_email(self, email: str) -> Optional[UserDomain]:
        db_user = self.db.query(DBUser).filter(DBUser.email == email).first()
        return self._to_domain(db_user) if db_user else None

    async def create(self, user: UserDomain) -> UserDomain:
        db_user = DBUser(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            google_oauth_id=user.google_oauth_id,
            role=user.role,
            created_at=user.created_at
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return self._to_domain(db_user)


class SqlAlchemySessionRepository(SessionRepository):
    def __init__(self, db: Session):
        self.db = db

    def _to_domain(self, db_sess: DBSession) -> SessionDomain:
        return SessionDomain(
            id=db_sess.id,
            user_id=db_sess.user_id,
            original_query=db_sess.original_query,
            status=db_sess.status,
            report_markdown=db_sess.report_markdown,
            created_at=db_sess.created_at
        )

    async def get_by_id(self, session_id: str) -> Optional[SessionDomain]:
        db_sess = self.db.query(DBSession).filter(DBSession.id == session_id).first()
        return self._to_domain(db_sess) if db_sess else None

    async def list_by_user_id(self, user_id: str) -> List[SessionDomain]:
        sessions = self.db.query(DBSession).filter(DBSession.user_id == user_id).all()
        return [self._to_domain(s) for s in sessions]

    async def create(self, session: SessionDomain) -> SessionDomain:
        db_sess = DBSession(
            id=session.id,
            user_id=session.user_id,
            original_query=session.original_query,
            status=session.status,
            report_markdown=session.report_markdown,
            created_at=session.created_at
        )
        self.db.add(db_sess)
        self.db.commit()
        self.db.refresh(db_sess)
        return self._to_domain(db_sess)

    async def update(self, session: SessionDomain) -> SessionDomain:
        db_sess = self.db.query(DBSession).filter(DBSession.id == session.id).first()
        if db_sess:
            db_sess.status = session.status
            db_sess.report_markdown = session.report_markdown
            self.db.commit()
            self.db.refresh(db_sess)
            return self._to_domain(db_sess)
        raise ValueError(f"Session with ID {session.id} not found.")


class SqlAlchemyFindingRepository(FindingRepository):
    def __init__(self, db: Session):
        self.db = db

    def _to_domain(self, f: DBFinding) -> FindingDomain:
        citations = [
            CitationDomain(
                id=c.id,
                finding_id=c.finding_id,
                source_title=c.source_title,
                source_url=c.source_url,
                citation_format=c.citation_format,
                quote=c.quote,
                created_at=c.created_at
            ) for c in f.citations
        ]
        return FindingDomain(
            id=f.id,
            session_id=f.session_id,
            claim=f.claim,
            confidence_score=float(f.confidence_score),
            source_count=f.source_count,
            source_quality_score=float(f.source_quality_score),
            verification_status=f.verification_status,
            consensus_rationale=f.consensus_rationale,
            citations=citations,
            created_at=f.created_at
        )

    async def create(self, finding: FindingDomain) -> FindingDomain:
        db_finding = DBFinding(
            id=finding.id,
            session_id=finding.session_id,
            claim=finding.claim,
            confidence_score=finding.confidence_score,
            source_count=finding.source_count,
            source_quality_score=finding.source_quality_score,
            verification_status=finding.verification_status,
            consensus_rationale=finding.consensus_rationale,
            created_at=finding.created_at
        )
        self.db.add(db_finding)
        self.db.commit()
        self.db.refresh(db_finding)
        return self._to_domain(db_finding)

    async def get_by_session_id(self, session_id: str) -> List[FindingDomain]:
        findings = self.db.query(DBFinding).filter(DBFinding.session_id == session_id).all()
        return [self._to_domain(f) for f in findings]


class SqlAlchemyCitationRepository(CitationRepository):
    def __init__(self, db: Session):
        self.db = db

    def _to_domain(self, c: DBCitation) -> CitationDomain:
        return CitationDomain(
            id=c.id,
            finding_id=c.finding_id,
            source_title=c.source_title,
            source_url=c.source_url,
            citation_format=c.citation_format,
            quote=c.quote,
            created_at=c.created_at
        )

    async def create(self, citation: CitationDomain) -> CitationDomain:
        db_citation = DBCitation(
            id=citation.id,
            finding_id=citation.finding_id,
            source_title=citation.source_title,
            source_url=citation.source_url,
            citation_format=citation.citation_format,
            quote=citation.quote,
            created_at=citation.created_at
        )
        self.db.add(db_citation)
        self.db.commit()
        self.db.refresh(db_citation)
        return self._to_domain(db_citation)

    async def get_by_finding_id(self, finding_id: str) -> List[CitationDomain]:
        citations = self.db.query(DBCitation).filter(DBCitation.finding_id == finding_id).all()
        return [self._to_domain(c) for c in citations]


class SqlAlchemyDocumentRepository(DocumentRepository):
    def __init__(self, db: Session):
        self.db = db

    def _to_domain(self, doc: DBDocument) -> DocumentDomain:
        return DocumentDomain(
            id=doc.id,
            session_id=doc.session_id,
            filename=doc.filename,
            file_type=doc.file_type,
            extracted_text=doc.extracted_text,
            created_at=doc.created_at
        )

    async def create(self, document: DocumentDomain) -> DocumentDomain:
        db_doc = DBDocument(
            id=document.id,
            session_id=document.session_id,
            filename=document.filename,
            file_type=document.file_type,
            extracted_text=document.extracted_text,
            created_at=document.created_at
        )
        self.db.add(db_doc)
        self.db.commit()
        self.db.refresh(db_doc)
        return self._to_domain(db_doc)

    async def list_by_session_id(self, session_id: str) -> List[DocumentDomain]:
        docs = self.db.query(DBDocument).filter(DBDocument.session_id == session_id).all()
        return [self._to_domain(d) for d in docs]


class SqlAlchemyMemoryRepository(MemoryRepository):
    def __init__(self, db: Session):
        self.db = db

    def _to_domain(self, mem: DBMemory) -> MemoryDomain:
        return MemoryDomain(
            id=mem.id,
            user_id=mem.user_id,
            content=mem.content,
            embedding=mem.embedding,
            created_at=mem.created_at
        )

    async def create(self, memory: MemoryDomain) -> MemoryDomain:
        db_mem = DBMemory(
            id=memory.id,
            user_id=memory.user_id,
            content=memory.content,
            embedding=memory.embedding,
            created_at=memory.created_at
        )
        self.db.add(db_mem)
        self.db.commit()
        self.db.refresh(db_mem)
        return self._to_domain(db_mem)

    async def search_similarity(self, user_id: str, query_embedding: List[float], limit: int = 5) -> List[MemoryDomain]:
        # pgvector query simulation. If SQLite fallback, we do a basic match or text query search.
        # Postgres vector similarity search would look like: 
        # db.query(DBMemory).filter(DBMemory.user_id == user_id).order_by(DBMemory.embedding.cosine_distance(query_embedding)).limit(limit)
        memories = self.db.query(DBMemory).filter(DBMemory.user_id == user_id).limit(limit).all()
        return [self._to_domain(m) for m in memories]

import uuid
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas import SessionCreate, SessionResponse, SessionDetailResponse
from backend.app.infrastructure.db.repositories import SqlAlchemySessionRepository
from backend.app.infrastructure.db.models import DBSession
from backend.app.domain.models import SessionDomain
from backend.app.utils.auth_helpers import get_current_user
from backend.app.infrastructure.db.models import DBUser as User
from backend.app.agents.manager import ResearchManager

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)


@router.post("/create", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_in: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new research session for the authenticated user."""
    repo = SqlAlchemySessionRepository(db)
    session_domain = SessionDomain(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        original_query=session_in.original_query,
        status="PENDING",
        report_markdown=None,
        created_at=datetime.utcnow()
    )

    saved = await repo.create(session_domain)
    logger.info(f"Session created: id={saved.id} user={current_user.id}")
    return saved


@router.get("/", response_model=list[SessionResponse])
async def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return")
):
    """
    List all research sessions for the authenticated user.
    Supports pagination via skip/limit query parameters.
    """
    sessions = (
        db.query(DBSession)
        .filter(DBSession.user_id == current_user.id)
        .order_by(DBSession.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return sessions


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve a specific research session with findings, citations, and logs."""
    db_session = db.query(DBSession).filter(
        DBSession.id == session_id,
        DBSession.user_id == current_user.id
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research session not found."
        )

    return db_session


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a research session and all associated data (cascade)."""
    db_session = db.query(DBSession).filter(
        DBSession.id == session_id,
        DBSession.user_id == current_user.id
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research session not found."
        )

    db.delete(db_session)
    db.commit()
    logger.info(f"Session deleted: id={session_id} user={current_user.id}")


@router.get("/{session_id}/research")
async def stream_research(
    session_id: str,
    citation_format: str = Query("APA", pattern="^(APA|IEEE)$", description="Citation format"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Execute the multi-agent research pipeline and stream agent events via SSE.
    
    Fixes: citation_format is now correctly forwarded to ResearchManager.
    Fixes: user_id is now passed so memory attribution is correct.
    """
    db_session = db.query(DBSession).filter(
        DBSession.id == session_id,
        DBSession.user_id == current_user.id
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research session not found."
        )

    if db_session.status == "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Research session has already been completed. Create a new session to run again."
        )

    logger.info(
        f"Starting research pipeline: session={session_id} "
        f"user={current_user.id} format={citation_format}"
    )

    async def event_generator():
        manager = ResearchManager(db)
        async for log_entry in manager.run_session(
            session_id=session_id,
            query=db_session.original_query,
            user_id=current_user.id,
            citation_format=citation_format
        ):
            yield f"data: {json.dumps(log_entry)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disables Nginx buffering for SSE
        }
    )

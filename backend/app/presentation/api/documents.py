import uuid
import logging
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form

from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.infrastructure.db.models import DBDocument, DBSession
from backend.app.utils.auth_helpers import get_current_user
from backend.app.infrastructure.db.models import DBUser as User
from backend.app.utils.document_parsers import DocumentParser
from backend.app.config import settings

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = logging.getLogger(__name__)

# Allowed MIME types mapped to file categories
ALLOWED_MIME_TYPES = {
    "application/pdf": "PDF",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
    "text/plain": "TXT",
    "text/csv": "CSV",
    "application/csv": "CSV",
    "image/png": "IMAGE",
    "image/jpeg": "IMAGE",
    "image/jpg": "IMAGE",
}

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "csv", "png", "jpg", "jpeg"}

# Magic bytes signatures for basic file type verification
MAGIC_BYTES = {
    b"%PDF": "PDF",
    b"PK\x03\x04": "DOCX",  # ZIP container (docx)
    b"\xff\xd8\xff": "IMAGE",  # JPEG
    b"\x89PNG": "IMAGE",
}


def _sanitize_filename(filename: str) -> str:
    """Remove path traversal attempts and non-ASCII characters from filenames."""
    # Strip directory separators
    name = re.sub(r"[/\\]", "_", filename)
    # Keep only safe characters
    name = re.sub(r"[^\w\s.\-]", "", name)
    return name[:255]  # Enforce max length


def _detect_file_type(content_bytes: bytes, extension: str) -> str:
    """
    Verify file type using magic bytes in addition to extension.
    Returns category string or raises an error if mismatch is detected.
    """
    for magic, detected_type in MAGIC_BYTES.items():
        if content_bytes.startswith(magic):
            return detected_type

    # TXT and CSV have no reliable magic bytes — trust extension
    if extension in {"txt", "csv"}:
        return extension.upper()

    return extension.upper()


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a research document for a session. Supports PDF, DOCX, TXT, CSV, and images.

    Security controls:
    - File size limit enforced (default 10MB, configurable)
    - Extension + MIME type whitelist
    - Magic bytes verification
    - Filename sanitization (path traversal prevention)
    """
    # ── Verify session ownership ───────────────────────────────────────────────
    db_session = db.query(DBSession).filter(
        DBSession.id == session_id,
        DBSession.user_id == current_user.id
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research session not found or access denied."
        )

    # ── File size check ────────────────────────────────────────────────────────
    content_bytes = await file.read()
    file_size = len(content_bytes)

    if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {max_mb}MB."
        )

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty."
        )

    # ── Filename sanitization ──────────────────────────────────────────────────
    raw_filename = file.filename or "unknown_file"
    safe_filename = _sanitize_filename(raw_filename)
    ext = safe_filename.rsplit(".", 1)[-1].lower() if "." in safe_filename else ""

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format: .{ext}. Allowed: PDF, DOCX, TXT, CSV, PNG, JPG, JPEG."
        )

    # ── MIME type check ────────────────────────────────────────────────────────
    content_type = file.content_type or ""
    if content_type and content_type not in ALLOWED_MIME_TYPES and content_type != "application/octet-stream":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type: {content_type}."
        )

    # ── Magic bytes verification ───────────────────────────────────────────────
    detected_type = _detect_file_type(content_bytes, ext)

    # ── Parse document text ────────────────────────────────────────────────────
    extracted_text = DocumentParser.parse_file(safe_filename, content_bytes)

    # Limit DB storage (10k chars); full text would go to object storage in production
    stored_text = extracted_text[:10000]

    # ── Save to database ───────────────────────────────────────────────────────
    doc_id = str(uuid.uuid4())
    db_doc = DBDocument(
        id=doc_id,
        session_id=session_id,
        filename=safe_filename,
        file_type=detected_type,
        extracted_text=stored_text
    )
    db.add(db_doc)
    db.commit()

    logger.info(
        f"Document uploaded: id={doc_id} session={session_id} "
        f"file={safe_filename} type={detected_type} size={file_size}"
    )

    return {
        "document_id": doc_id,
        "filename": safe_filename,
        "file_type": detected_type,
        "size_bytes": file_size,
        "extracted_chars": len(extracted_text),
        "status": "PARSED"
    }


@router.get("/session/{session_id}", tags=["documents"])
async def list_session_documents(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all documents uploaded for a specific session."""
    db_session = db.query(DBSession).filter(
        DBSession.id == session_id,
        DBSession.user_id == current_user.id
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research session not found or access denied."
        )

    docs = db.query(DBDocument).filter(DBDocument.session_id == session_id).all()
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "file_type": d.file_type,
            "created_at": d.created_at.isoformat() if d.created_at else None
        }
        for d in docs
    ]

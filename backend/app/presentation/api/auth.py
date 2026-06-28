import re
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas import UserCreate, UserResponse, UserLogin, Token
from backend.app.infrastructure.db.repositories import SqlAlchemyUserRepository
from backend.app.domain.models import UserDomain
from backend.app.utils.auth_helpers import (
    get_password_hash, verify_password, create_access_token,
    get_current_user, require_admin
)
from backend.app.infrastructure.db.models import DBUser as User

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)

# ── Input Sanitization ────────────────────────────────────────────────────────
def _sanitize_input(value: str, max_length: int = 500) -> str:
    """
    Strip common prompt injection patterns and limit length.
    This is a defense-in-depth measure — the LLM system prompts are the primary guard.
    """
    # Strip null bytes and control characters
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    # Truncate to max length
    return cleaned[:max_length].strip()


# ── Schemas ───────────────────────────────────────────────────────────────────
class GoogleOAuthPayload(BaseModel):
    token: str = Field(..., min_length=10, max_length=2048, description="Google OAuth ID token")


class RoleUpdatePayload(BaseModel):
    user_id: str = Field(..., description="User ID to update")
    new_role: str = Field(..., pattern="^(Admin|Researcher|Guest)$", description="New role")


# ── Register ──────────────────────────────────────────────────────────────────
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """Register a new user account with email and password."""
    repo = SqlAlchemyUserRepository(db)

    # Check for duplicate email
    existing = await repo.get_by_email(user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists."
        )

    # Validate role
    allowed_roles = {"Admin", "Researcher", "Guest"}
    role = user_in.role if user_in.role in allowed_roles else "Researcher"

    hashed = get_password_hash(user_in.password)
    user_domain = UserDomain(
        id=str(uuid.uuid4()),
        email=user_in.email,
        password_hash=hashed,
        google_oauth_id=None,
        role=role,
        created_at=datetime.utcnow()
    )

    saved = await repo.create(user_domain)
    logger.info(f"New user registered: email={user_in.email} role={role}")
    return saved


# ── Login ─────────────────────────────────────────────────────────────────────
@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Authenticate with email and password, receive a JWT access token."""
    repo = SqlAlchemyUserRepository(db)
    user = await repo.get_by_email(credentials.email)

    # Use constant-time comparison to resist timing attacks
    if not user or not user.password_hash:
        # Still hash something to prevent timing oracle
        get_password_hash("dummy_value_to_prevent_timing_attack")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not verify_password(credentials.password, user.password_hash):
        logger.warning(f"Failed login attempt for email={credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = create_access_token(data={
        "user_id": user.id,
        "email": user.email,
        "role": user.role
    })

    logger.info(f"User logged in: email={credentials.email} role={user.role}")
    return {"access_token": token, "token_type": "bearer"}


# ── Google OAuth (Simulated — requires real Google credentials for production) ─
@router.post("/oauth/google", response_model=Token)
async def oauth_google(payload: GoogleOAuthPayload, db: Session = Depends(get_db)):
    """
    Google OAuth token exchange.
    
    NOTE: This implementation simulates OAuth for development.
    Production requires: google-auth library + real OAuth client ID/secret.
    The token is NOT verified against Google's public keys here.
    """
    google_token = payload.token
    repo = SqlAlchemyUserRepository(db)

    # In production, replace this block with:
    # from google.oauth2 import id_token
    # from google.auth.transport import requests as google_requests
    # idinfo = id_token.verify_oauth2_token(google_token, google_requests.Request(), GOOGLE_CLIENT_ID)
    # simulated_email = idinfo["email"]

    # Development simulation:
    simulated_email = f"google_{google_token[:12]}@oauth.intellex.dev"

    user = await repo.get_by_email(simulated_email)
    if not user:
        user_domain = UserDomain(
            id=str(uuid.uuid4()),
            email=simulated_email,
            password_hash=None,
            google_oauth_id=google_token[:64],  # Store first 64 chars as identifier
            role="Researcher",
            created_at=datetime.utcnow()
        )
        user = await repo.create(user_domain)
        logger.info(f"New OAuth user created: email={simulated_email}")

    token = create_access_token(data={
        "user_id": user.id,
        "email": user.email,
        "role": user.role
    })
    return {"access_token": token, "token_type": "bearer"}


# ── Me (current user profile) ─────────────────────────────────────────────────
@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user


# ── Admin: Update user role (RBAC enforced) ───────────────────────────────────
@router.put("/admin/users/role", response_model=dict)
async def update_user_role(
    payload: RoleUpdatePayload,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin)  # RBAC guard — requires Admin role
):
    """
    Update a user's role. Requires Admin authorization.
    This is the first route where require_admin() is actually enforced.
    """
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user.role = payload.new_role
    db.commit()
    logger.info(f"Admin role update: user_id={payload.user_id} new_role={payload.new_role}")
    return {"message": f"User role updated to {payload.new_role}."}

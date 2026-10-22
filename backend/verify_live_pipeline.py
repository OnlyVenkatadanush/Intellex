"""
Verification script for end-to-end autonomous research workflow
Tests real retrieval, LLM reasoning, debate generation, and DB persistence.
"""
import asyncio
import os
import sys
from datetime import datetime

# Set up python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.app.config import settings
from backend.app.database import engine, SessionLocal, init_db
from backend.app.infrastructure.db.models import DBSession, DBUser
from backend.app.agents.manager import ResearchManager
from backend.app.utils.auth_helpers import get_password_hash

async def run_verification():
    print("=" * 60)
    print("INTELLEX ENTERPRISE SYSTEM VERIFICATION")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Active LLM Provider: {settings.LLM_PROVIDER.upper()} ({settings.GROQ_MODEL if settings.LLM_PROVIDER == 'groq' else settings.GEMINI_MODEL})")
    print("=" * 60)

    # 1. Initialize DB and apply migrations
    init_db(engine)
    db = SessionLocal()
    
    try:
        # 2. Ensure test researcher user exists
        user = db.query(DBUser).filter(DBUser.email == "researcher@intellex.ai").first()
        if not user:
            user = DBUser(
                email="researcher@intellex.ai",
                password_hash=get_password_hash("ResearchPass123!"),
                role="Researcher"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"[+] Researcher account verified: {user.email}")
        else:
            print(f"[+] Researcher account already present: {user.email}")

        # 3. Create a test session
        test_session = DBSession(
            user_id=user.id,
            original_query="Evaluate safety, ionic conductivity, and interfacial dendrite suppression mechanisms in solid-state lithium metal batteries.",
            status="PENDING"
        )
        db.add(test_session)
        db.commit()
        db.refresh(test_session)
        print(f"[+] Created research session ID: {test_session.id}")

        # 4. Run the full live pipeline through ResearchManager
        manager = ResearchManager(db)
        print("\n[*] Starting autonomous 8-stage agent orchestration (streaming logs)...")

        log_count = 0
        async for log in manager.run_session(
            session_id=test_session.id,
            query=test_session.original_query,
            user_id=user.id
        ):
            log_count += 1
            agent_name = log.get("agent_name", "Agent")
            agent_role = log.get("agent_role", "")
            msg = log.get("message", "")
            log_type = log.get("log_type", "INFO")
            print(f"    [{log_count:02d}] [{agent_name} - {agent_role}] ({log_type}): {msg}")

        print("\n" + "=" * 60)
        print("RESEARCH RESULTS SUMMARY")
        print("=" * 60)
        
        # Verify persistence in DB
        db.refresh(test_session)
        print(f"DB Persisted Status: {test_session.status}")
        print(f"DB Findings Count: {len(test_session.findings)}")
        total_citations = sum(len(f.citations) for f in test_session.findings)
        print(f"DB Citations Count: {total_citations}")
        print(f"Report Length: {len(test_session.report_markdown or '')} characters")
        if test_session.report_markdown:
            print(f"\nReport Preview:\n{test_session.report_markdown[:350]}...\n")

        assert test_session.status == "COMPLETED", f"Session status is {test_session.status}, expected COMPLETED"
        assert len(test_session.findings) > 0, "No findings were persisted"
        print("\n[SUCCESS] Enterprise end-to-end live pipeline executed cleanly without errors!")
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_verification())

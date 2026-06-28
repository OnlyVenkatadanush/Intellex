"""
backend/tests/conftest.py

Shared pytest fixtures for Intellex test suite.

Fixtures:
  - db_session: In-memory SQLite session (transactional, auto-rollback)
  - test_client: TestClient with a fresh database per test
  - mock_llm: Mock LLM provider that returns deterministic structured output
  - test_user: A registered test user
  - auth_headers: JWT auth headers for the test user
"""

import pytest
import uuid
from datetime import datetime
from typing import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Override DATABASE_URL before importing app modules
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test_secret_key_for_testing_only"
os.environ["GEMINI_API_KEY"] = ""  # Disable real LLM calls during tests
os.environ["ENVIRONMENT"] = "test"

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.infrastructure.db.models import DBUser
import backend.app.infrastructure.db.graph_models  # noqa: Ensure tables registered


# ── In-memory SQLite engine for tests ─────────────────────────────────────────
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Creates all tables in an in-memory SQLite DB and provides a session.
    Rolls back after each test to ensure test isolation.
    """
    Base.metadata.create_all(bind=TEST_ENGINE)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture(scope="function")
def test_client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    FastAPI TestClient that uses the in-memory test database.
    Overrides the get_db dependency to inject the test session.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # Rollback handled by db_session fixture

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def registered_user(test_client: TestClient) -> dict:
    """Register and return a test user."""
    response = test_client.post("/api/auth/register", json={
        "email": "test@intellex.dev",
        "password": "TestPassword123!",
        "role": "Researcher"
    })
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def auth_headers(test_client: TestClient, registered_user: dict) -> dict:
    """Get JWT auth headers for the test user."""
    response = test_client.post("/api/auth/login", json={
        "email": "test@intellex.dev",
        "password": "TestPassword123!"
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_session(test_client: TestClient, auth_headers: dict) -> dict:
    """Create and return a test research session."""
    response = test_client.post(
        "/api/sessions/create",
        json={"original_query": "Test research query about AI agents"},
        headers=auth_headers
    )
    assert response.status_code == 201
    return response.json()


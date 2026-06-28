"""
backend/tests/test_api.py

Integration tests for the Intellex API.
Run with: pytest backend/tests/test_api.py -v
"""

import pytest
import io


# ═══════════════════════════════════════════════════════════════════════════
# Auth Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestAuthRegister:
    def test_register_success(self, test_client):
        response = test_client.post("/api/auth/register", json={
            "email": "newuser@test.com",
            "password": "Password123!",
            "role": "Researcher"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@test.com"
        assert data["role"] == "Researcher"
        assert "id" in data
        assert "password_hash" not in data  # Must not leak hash

    def test_register_duplicate_email(self, test_client, registered_user):
        response = test_client.post("/api/auth/register", json={
            "email": "test@intellex.dev",
            "password": "AnotherPassword123!",
            "role": "Researcher"
        })
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    def test_register_short_password(self, test_client):
        response = test_client.post("/api/auth/register", json={
            "email": "short@test.com",
            "password": "ab"
        })
        assert response.status_code == 422  # Pydantic validation error

    def test_register_invalid_email(self, test_client):
        response = test_client.post("/api/auth/register", json={
            "email": "not-an-email",
            "password": "ValidPassword123!"
        })
        assert response.status_code == 422


class TestAuthLogin:
    def test_login_success(self, test_client, registered_user):
        response = test_client.post("/api/auth/login", json={
            "email": "test@intellex.dev",
            "password": "TestPassword123!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, test_client, registered_user):
        response = test_client.post("/api/auth/login", json={
            "email": "test@intellex.dev",
            "password": "WrongPassword!"
        })
        assert response.status_code == 401

    def test_login_unknown_email(self, test_client):
        response = test_client.post("/api/auth/login", json={
            "email": "nobody@nowhere.com",
            "password": "Password123!"
        })
        assert response.status_code == 401

    def test_get_me(self, test_client, auth_headers):
        response = test_client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@intellex.dev"


# ═══════════════════════════════════════════════════════════════════════════
# Session Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSessions:
    def test_create_session(self, test_client, auth_headers):
        response = test_client.post(
            "/api/sessions/create",
            json={"original_query": "Impact of transformer architectures on NLP"},
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["original_query"] == "Impact of transformer architectures on NLP"
        assert data["status"] == "PENDING"
        assert "id" in data

    def test_create_session_unauthenticated(self, test_client):
        response = test_client.post(
            "/api/sessions/create",
            json={"original_query": "Some query"}
        )
        assert response.status_code == 401

    def test_list_sessions(self, test_client, auth_headers, test_session):
        response = test_client.get("/api/sessions/", headers=auth_headers)
        assert response.status_code == 200
        sessions = response.json()
        assert isinstance(sessions, list)
        assert len(sessions) >= 1
        assert sessions[0]["id"] == test_session["id"]

    def test_list_sessions_pagination(self, test_client, auth_headers):
        # Create 3 sessions
        for i in range(3):
            test_client.post(
                "/api/sessions/create",
                json={"original_query": f"Query {i}"},
                headers=auth_headers
            )

        response = test_client.get("/api/sessions/?limit=2", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) <= 2

    def test_get_session(self, test_client, auth_headers, test_session):
        session_id = test_session["id"]
        response = test_client.get(f"/api/sessions/{session_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == session_id

    def test_get_session_not_found(self, test_client, auth_headers):
        response = test_client.get("/api/sessions/nonexistent-id", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_session(self, test_client, auth_headers, test_session):
        session_id = test_session["id"]
        response = test_client.delete(f"/api/sessions/{session_id}", headers=auth_headers)
        assert response.status_code == 204

        # Verify it's gone
        response = test_client.get(f"/api/sessions/{session_id}", headers=auth_headers)
        assert response.status_code == 404

    def test_session_isolation(self, test_client, auth_headers, test_session):
        """A user cannot access another user's sessions."""
        # Create second user
        test_client.post("/api/auth/register", json={
            "email": "other@test.com",
            "password": "OtherPassword123!",
            "role": "Researcher"
        })
        other_login = test_client.post("/api/auth/login", json={
            "email": "other@test.com",
            "password": "OtherPassword123!"
        })
        other_token = other_login.json()["access_token"]
        other_headers = {"Authorization": f"Bearer {other_token}"}

        # Other user tries to access first user's session
        session_id = test_session["id"]
        response = test_client.get(f"/api/sessions/{session_id}", headers=other_headers)
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# Document Upload Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestDocuments:
    def test_upload_txt_document(self, test_client, auth_headers, test_session):
        session_id = test_session["id"]
        file_content = b"This is a test text document about AI research."

        response = test_client.post(
            "/api/documents/upload",
            data={"session_id": session_id},
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
            headers=auth_headers
        )
        assert response.status_code == 202
        data = response.json()
        assert data["file_type"] == "TXT"
        assert data["status"] == "PARSED"
        assert "document_id" in data

    def test_upload_rejected_extension(self, test_client, auth_headers, test_session):
        session_id = test_session["id"]
        response = test_client.post(
            "/api/documents/upload",
            data={"session_id": session_id},
            files={"file": ("malware.exe", io.BytesIO(b"evil"), "application/octet-stream")},
            headers=auth_headers
        )
        assert response.status_code == 400

    def test_upload_empty_file(self, test_client, auth_headers, test_session):
        session_id = test_session["id"]
        response = test_client.post(
            "/api/documents/upload",
            data={"session_id": session_id},
            files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
            headers=auth_headers
        )
        assert response.status_code == 400

    def test_upload_wrong_session(self, test_client, auth_headers):
        response = test_client.post(
            "/api/documents/upload",
            data={"session_id": "non-existent-session"},
            files={"file": ("test.txt", io.BytesIO(b"content"), "text/plain")},
            headers=auth_headers
        )
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# Health Check Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestHealth:
    def test_health_check(self, test_client):
        response = test_client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_detailed_health_check(self, test_client):
        response = test_client.get("/api/health/detailed")
        assert response.status_code == 200
        data = response.json()
        assert "components" in data
        assert "database" in data["components"]
        assert data["components"]["database"]["status"] == "healthy"

    def test_root_endpoint(self, test_client):
        response = test_client.get("/")
        assert response.status_code == 200
        assert "service" in response.json()


# ═══════════════════════════════════════════════════════════════════════════
# Analytics Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestAnalytics:
    def test_knowledge_graph_returns_structure(self, test_client, auth_headers, test_session):
        session_id = test_session["id"]
        response = test_client.get(f"/api/sessions/{session_id}/graph", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert data["session_id"] == session_id

    def test_replay_timeline_returns_structure(self, test_client, auth_headers, test_session):
        session_id = test_session["id"]
        response = test_client.get(f"/api/sessions/{session_id}/replay", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "timeline" in data
        assert "total_steps" in data

    def test_compare_sessions(self, test_client, auth_headers):
        # Create two sessions
        s1 = test_client.post(
            "/api/sessions/create",
            json={"original_query": "AI in healthcare"},
            headers=auth_headers
        ).json()
        s2 = test_client.post(
            "/api/sessions/create",
            json={"original_query": "AI in medical diagnosis"},
            headers=auth_headers
        ).json()

        response = test_client.get(
            f"/api/sessions/{s1['id']}/compare/{s2['id']}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "new_claims" in data
        assert "removed_claims" in data
        assert "summary" in data

    def test_memory_endpoint(self, test_client, auth_headers, test_session):
        session_id = test_session["id"]
        response = test_client.get(f"/api/sessions/{session_id}/memory", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "memories" in data
        assert isinstance(data["memories"], list)

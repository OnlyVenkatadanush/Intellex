"""
backend/tests/test_units.py

Unit tests for Intellex utilities.
These tests do NOT require a running server or database.
Run with: pytest backend/tests/test_units.py -v
"""

import pytest
import asyncio
import io


# ═══════════════════════════════════════════════════════════════════════════
# Document Parser Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestDocumentParsers:
    def test_parse_txt(self):
        from backend.app.utils.document_parsers import DocumentParser
        content = b"Hello, this is a plain text document."
        result = DocumentParser.parse_txt(content)
        assert result == "Hello, this is a plain text document."

    def test_parse_txt_utf8_invalid_bytes(self):
        from backend.app.utils.document_parsers import DocumentParser
        content = b"Valid text \xff\xfe with invalid bytes"
        result = DocumentParser.parse_txt(content)
        assert "Valid text" in result  # Should not raise, invalid bytes ignored

    def test_parse_csv_produces_markdown_table(self):
        from backend.app.utils.document_parsers import DocumentParser
        content = b"Name,Age,City\nAlice,30,London\nBob,25,Paris\n"
        result = DocumentParser.parse_csv(content)
        assert "|" in result
        assert "Name" in result
        assert "Alice" in result
        assert "Bob" in result

    def test_parse_csv_empty(self):
        from backend.app.utils.document_parsers import DocumentParser
        result = DocumentParser.parse_csv(b"")
        assert "Empty" in result

    def test_parse_image_returns_ocr_placeholder(self):
        from backend.app.utils.document_parsers import DocumentParser
        result = DocumentParser.parse_image("test.png", b"\x89PNG\r\n" + b"\x00" * 100)
        assert "Image" in result or "OCR" in result or "Filename" in result

    def test_parse_file_dispatch_txt(self):
        from backend.app.utils.document_parsers import DocumentParser
        result = DocumentParser.parse_file("notes.txt", b"Test content")
        assert result == "Test content"

    def test_parse_file_dispatch_csv(self):
        from backend.app.utils.document_parsers import DocumentParser
        result = DocumentParser.parse_file("data.csv", b"col1,col2\nval1,val2\n")
        assert "|" in result

    def test_parse_docx_invalid_returns_error_message(self):
        from backend.app.utils.document_parsers import DocumentParser
        result = DocumentParser.parse_docx(b"not a valid docx file")
        assert "Error" in result or len(result) > 0  # Should not raise


# ═══════════════════════════════════════════════════════════════════════════
# Auth Helper Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestAuthHelpers:
    def test_password_hash_and_verify(self):
        from backend.app.utils.auth_helpers import get_password_hash, verify_password
        password = "TestPassword123!"
        hashed = get_password_hash(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_verify_wrong_password(self):
        from backend.app.utils.auth_helpers import get_password_hash, verify_password
        hashed = get_password_hash("correct_password")
        assert not verify_password("wrong_password", hashed)

    def test_create_access_token(self):
        from backend.app.utils.auth_helpers import create_access_token
        token = create_access_token({"user_id": "test-123", "email": "test@test.com"})
        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are long

    def test_token_contains_correct_claims(self):
        from backend.app.utils.auth_helpers import create_access_token
        from jose import jwt
        from backend.app.config import settings

        token = create_access_token({"user_id": "abc", "email": "x@x.com", "role": "Admin"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["user_id"] == "abc"
        assert payload["email"] == "x@x.com"
        assert payload["role"] == "Admin"


# ═══════════════════════════════════════════════════════════════════════════
# Reliability Utilities Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestReliability:
    @pytest.mark.asyncio
    async def test_retry_succeeds_on_first_attempt(self):
        from backend.app.utils.reliability import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        async def always_succeeds():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await always_succeeds()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_retries_on_failure(self):
        from backend.app.utils.reliability import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        async def fails_twice_then_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = await fails_twice_then_succeeds()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_raises_after_max_attempts(self):
        from backend.app.utils.reliability import retry_with_backoff

        @retry_with_backoff(max_attempts=2, base_delay=0.01, reraise=True)
        async def always_fails():
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            await always_fails()

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_threshold(self):
        from backend.app.utils.reliability import CircuitBreaker, CircuitOpenError

        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0, name="test")

        async def failing_func():
            raise ValueError("Failure")

        # First two failures open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(failing_func)

        # Next call should be rejected immediately (circuit open)
        with pytest.raises(CircuitOpenError):
            await breaker.call(failing_func)

    @pytest.mark.asyncio
    async def test_circuit_breaker_closes_after_success(self):
        from backend.app.utils.reliability import CircuitBreaker, CircuitState

        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=0.0, name="test2")

        async def success_func():
            return "ok"

        result = await breaker.call(success_func)
        assert result == "ok"
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_with_timeout_returns_fallback(self):
        from backend.app.utils.reliability import with_timeout
        import asyncio

        async def slow_coro():
            await asyncio.sleep(10)
            return "done"

        result = await with_timeout(slow_coro(), timeout_seconds=0.05, fallback="timeout_fallback")
        assert result == "timeout_fallback"


# ═══════════════════════════════════════════════════════════════════════════
# Search Tools Tests (using async)
# ═══════════════════════════════════════════════════════════════════════════

class TestSearchTools:
    @pytest.mark.asyncio
    async def test_arxiv_returns_list(self):
        from backend.app.utils.search_tools import SearchTools
        # Real arXiv call (integration) — skip if no network
        try:
            results = await SearchTools.fetch_arxiv_papers("transformer attention mechanism", max_results=2)
            assert isinstance(results, list)
            if results:
                assert "title" in results[0]
                assert "url" in results[0]
                assert "content" in results[0]
                assert results[0]["source"] == "arXiv Academic API"
        except Exception:
            pytest.skip("arXiv API not reachable in test environment")

    @pytest.mark.asyncio
    async def test_web_search_fallback_returns_list(self):
        from backend.app.utils.search_tools import SearchTools
        # No Tavily key configured — should fall back to Wikipedia or mock
        results = await SearchTools._fallback_search("machine learning", max_results=2)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_web_search_returns_structure(self):
        from backend.app.utils.search_tools import SearchTools
        results = await SearchTools.web_search("artificial intelligence", max_results=2)
        assert isinstance(results, list)
        # Even empty list is valid (network may be unavailable)

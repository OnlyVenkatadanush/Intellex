"""
backend/app/utils/reliability.py

Reliability primitives:
- retry_with_backoff: exponential backoff + jitter decorator for LLM / external API calls
- CircuitBreaker: simple circuit breaker with half-open recovery
- with_timeout: timeout wrapper for any coroutine

Usage:
    @retry_with_backoff(max_attempts=3, base_delay=1.0, exceptions=(httpx.TimeoutException,))
    async def call_external_api(): ...

    breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)
    result = await breaker.call(call_external_api)
"""

import asyncio
import logging
import random
import time
from enum import Enum
from functools import wraps
from typing import Callable, Tuple, Type, Any

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    reraise: bool = True
):
    """
    Decorator that retries an async function with exponential backoff and jitter.

    Args:
        max_attempts: Total number of attempts (including the first one)
        base_delay: Initial delay in seconds between retries
        max_delay: Maximum delay cap in seconds
        exceptions: Tuple of exception types to retry on
        reraise: If True, reraises the exception after all attempts fail
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        logger.error(
                            f"[Retry] {func.__name__} failed after {max_attempts} attempts: {exc}"
                        )
                        if reraise:
                            raise
                        return None

                    # Exponential backoff with full jitter
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    jitter = random.uniform(0, delay * 0.3)  # ±30% jitter
                    sleep_time = delay + jitter

                    logger.warning(
                        f"[Retry] {func.__name__} attempt {attempt}/{max_attempts} "
                        f"failed ({exc}). Retrying in {sleep_time:.2f}s..."
                    )
                    await asyncio.sleep(sleep_time)

            if reraise and last_exc:
                raise last_exc
            return None
        return wrapper
    return decorator


class CircuitState(Enum):
    CLOSED = "CLOSED"       # Normal operation
    OPEN = "OPEN"           # Failing — reject calls immediately
    HALF_OPEN = "HALF_OPEN" # Recovery probe — allow one call through


class CircuitBreaker:
    """
    Circuit breaker for protecting external service calls.

    States:
    - CLOSED: Calls pass through normally
    - OPEN: Calls fail immediately (CircuitOpenError raised)
    - HALF_OPEN: One probe call allowed to test recovery
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        name: str = "default"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                logger.info(f"[CircuitBreaker:{self.name}] Transitioning to HALF_OPEN")
                self._state = CircuitState.HALF_OPEN
        return self._state

    def _record_success(self):
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        logger.debug(f"[CircuitBreaker:{self.name}] Call succeeded — state: CLOSED")

    def _record_failure(self, exc: Exception):
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.error(
                f"[CircuitBreaker:{self.name}] Circuit OPENED after "
                f"{self._failure_count} failures. Last error: {exc}"
            )

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute func through the circuit breaker."""
        current_state = self.state

        if current_state == CircuitState.OPEN:
            raise CircuitOpenError(
                f"Circuit breaker '{self.name}' is OPEN. "
                f"Retry after {self.recovery_timeout}s."
            )

        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as exc:
            self._record_failure(exc)
            raise


class CircuitOpenError(Exception):
    """Raised when a circuit breaker is in the OPEN state."""
    pass


async def with_timeout(coro, timeout_seconds: float, fallback=None):
    """
    Execute a coroutine with a timeout. Returns fallback value on timeout.
    
    Usage:
        result = await with_timeout(call_llm(...), timeout_seconds=20.0, fallback="")
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(f"Operation timed out after {timeout_seconds}s")
        return fallback


# ── Pre-configured circuit breakers for external services ─────────────────────
gemini_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60.0,
    name="gemini-api"
)

arxiv_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=30.0,
    name="arxiv-api"
)

pubmed_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=30.0,
    name="pubmed-api"
)

tavily_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=30.0,
    name="tavily-api"
)

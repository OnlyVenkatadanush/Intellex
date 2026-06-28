import httpx
import json
import logging
from typing import Type, TypeVar
from pydantic import BaseModel

from backend.app.domain.llm_provider import LLMProvider
from backend.app.config import settings
from backend.app.utils.reliability import (
    retry_with_backoff, gemini_breaker, with_timeout, CircuitOpenError
)

logger = logging.getLogger(__name__)
T = TypeVar('T', bound=BaseModel)

LLM_TIMEOUT_SECONDS = 30.0
LLM_MAX_RETRIES = 3


class GeminiProvider(LLMProvider):
    def __init__(self, model: str = None):
        self.api_key = settings.GEMINI_API_KEY
        # Model is configurable — not hardcoded
        self.model = model or "gemini-1.5-flash"
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    @retry_with_backoff(
        max_attempts=LLM_MAX_RETRIES,
        base_delay=1.5,
        exceptions=(httpx.TimeoutException, httpx.ConnectError, ValueError)
    )
    async def generate_text(self, prompt: str, system_prompt: str, temperature: float = 0.2) -> str:
        if not self.api_key:
            raise ValueError("Gemini API key is not configured.")

        url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_prompt}\n\nUser Request:\n{prompt}"}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 4096
            }
        }

        async def _do_request():
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=body,
                    timeout=LLM_TIMEOUT_SECONDS
                )
                if response.status_code == 200:
                    res_json = response.json()
                    try:
                        return res_json["candidates"][0]["content"]["parts"][0]["text"]
                    except (KeyError, IndexError) as exc:
                        raise ValueError(f"Unexpected Gemini response format: {res_json}") from exc
                elif response.status_code == 429:
                    raise ValueError(f"Gemini rate limited (429). Backing off.")
                else:
                    raise ValueError(
                        f"Gemini API error: status={response.status_code} body={response.text[:200]}"
                    )

        try:
            result = await gemini_breaker.call(_do_request)
            logger.debug(f"Gemini generate_text: model={self.model} prompt_len={len(prompt)}")
            return result
        except CircuitOpenError as exc:
            raise ValueError(f"Gemini circuit breaker open: {exc}") from exc

    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str,
        response_model: Type[T],
        temperature: float = 0.2
    ) -> T:
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        structured_system_prompt = (
            f"{system_prompt}\n\n"
            f"IMPORTANT: Respond with a single valid JSON object that strictly matches this schema:\n"
            f"{schema_json}\n"
            f"Rules: No markdown fences, no explanations, only valid JSON."
        )

        response_text = await self.generate_text(prompt, structured_system_prompt, temperature)

        # Clean common Gemini markdown wrapping
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            # Strip opening and closing fence
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            parsed_json = json.loads(cleaned)
            return response_model.model_validate(parsed_json)
        except (json.JSONDecodeError, Exception) as exc:
            logger.error(
                f"Gemini structured parse failed. "
                f"Model: {response_model.__name__}. Raw: {cleaned[:300]}. Error: {exc}"
            )
            raise ValueError(f"Failed to parse Gemini structured response: {exc}") from exc

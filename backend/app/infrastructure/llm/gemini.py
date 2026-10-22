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


def _extract_json_block(text: str) -> str:
    cleaned = text.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()
    
    start_brace = cleaned.find('{')
    start_bracket = cleaned.find('[')
    if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
        end_brace = cleaned.rfind('}')
        if end_brace != -1:
            return cleaned[start_brace:end_brace+1]
    elif start_bracket != -1:
        end_bracket = cleaned.rfind(']')
        if end_bracket != -1:
            return cleaned[start_bracket:end_bracket+1]
    return cleaned


class GeminiProvider(LLMProvider):
    def __init__(self, model: str = None):
        self.api_key = settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self.fallback_model = settings.GEMINI_FALLBACK_MODEL
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    @retry_with_backoff(
        max_attempts=LLM_MAX_RETRIES,
        base_delay=1.5,
        exceptions=(httpx.TimeoutException, httpx.ConnectError, ValueError)
    )
    async def _execute_request(self, model: str, prompt: str, system_prompt: str, temperature: float = 0.2) -> str:
        url = f"{self.base_url}/{model}:generateContent?key={self.api_key}"
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_prompt}\n\nUser Request:\n{prompt}"}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 8192
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
                    await asyncio.sleep(2.0)
                    raise ValueError("Gemini rate limited (429). Backing off.")
                else:
                    raise ValueError(
                        f"Gemini API error ({model}): status={response.status_code} body={response.text[:200]}"
                    )

        return await gemini_breaker.call(_do_request)

    async def generate_text(self, prompt: str, system_prompt: str, temperature: float = 0.2) -> str:
        if not self.api_key:
            if settings.ENVIRONMENT == "test":
                from backend.app.infrastructure.llm.manager import MockProvider
                return await MockProvider().generate_text(prompt, system_prompt, temperature)
            raise ValueError("Gemini API key is not configured in settings.")

        # 1. Try primary model
        try:
            return await self._execute_request(self.model, prompt, system_prompt, temperature)
        except Exception as exc:
            logger.warning(f"Primary model {self.model} failed: {exc}. Trying fallback {self.fallback_model}...")

        # 2. Try fallback model if different
        if self.fallback_model and self.fallback_model != self.model:
            try:
                return await self._execute_request(self.fallback_model, prompt, system_prompt, temperature)
            except Exception as fb_exc:
                logger.error(f"Fallback model {self.fallback_model} also failed: {fb_exc}")

        # 3. Test environment fallback only
        if settings.ENVIRONMENT == "test":
            from backend.app.infrastructure.llm.manager import MockProvider
            return await MockProvider().generate_text(prompt, system_prompt, temperature)

        raise RuntimeError(f"All Gemini LLM generation attempts failed for model {self.model}.")

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
            f"Rules: Return ONLY raw JSON. No markdown code fences, no explanations, no text before or after."
        )

        try:
            response_text = await self.generate_text(prompt, structured_system_prompt, temperature)
            cleaned = _extract_json_block(response_text)
            parsed_json = json.loads(cleaned)
            return response_model.model_validate(parsed_json)
        except Exception as exc:
            logger.warning(
                f"Gemini structured generation attempt 1 failed: {exc}. Retrying with strict JSON instruction..."
            )
            # Retry with explicit JSON repair prompt
            try:
                repair_prompt = f"{prompt}\n\nPlease output valid JSON matching schema: {schema_json}"
                response_text = await self.generate_text(repair_prompt, "You are a JSON formatter. Output only JSON.", temperature=0.1)
                cleaned = _extract_json_block(response_text)
                parsed_json = json.loads(cleaned)
                return response_model.model_validate(parsed_json)
            except Exception as rep_exc:
                logger.error(f"Structured generation failed for {response_model.__name__}: {rep_exc}")
                if settings.ENVIRONMENT == "test":
                    from backend.app.infrastructure.llm.manager import MockProvider
                    return await MockProvider().generate_structured(prompt, system_prompt, response_model, temperature)
                raise rep_exc

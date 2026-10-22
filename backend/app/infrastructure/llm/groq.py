import httpx
import json
import logging
from typing import Type, TypeVar
from pydantic import BaseModel

from backend.app.domain.llm_provider import LLMProvider
from backend.app.config import settings
from backend.app.utils.reliability import (
    retry_with_backoff, groq_breaker, with_timeout, CircuitOpenError
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


class GroqProvider(LLMProvider):
    """
    High-performance, low-latency LLM provider running on Groq Cloud.
    Supports 120B/20B open-weights reasoning models with sub-second latency.
    """
    def __init__(self, model: str = None):
        self.api_key = settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL
        self.fallback_model = settings.GROQ_FALLBACK_MODEL
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    @retry_with_backoff(
        max_attempts=LLM_MAX_RETRIES,
        base_delay=1.0,
        exceptions=(httpx.TimeoutException, httpx.ConnectError, ValueError)
    )
    async def _execute_request(
        self,
        model: str,
        messages: list,
        temperature: float = 0.2,
        json_mode: bool = False
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async def _do_request():
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=LLM_TIMEOUT_SECONDS
                )
                if response.status_code == 200:
                    data = response.json()
                    try:
                        return data["choices"][0]["message"]["content"]
                    except (KeyError, IndexError) as exc:
                        raise ValueError(f"Unexpected Groq response format: {data}") from exc
                elif response.status_code == 429:
                    raise ValueError("Groq rate limited (429).")
                else:
                    raise ValueError(
                        f"Groq API error ({model}): status={response.status_code} body={response.text[:200]}"
                    )

        return await groq_breaker.call(_do_request)

    async def generate_text(self, prompt: str, system_prompt: str, temperature: float = 0.2) -> str:
        if not self.api_key:
            if settings.ENVIRONMENT == "test":
                from backend.app.infrastructure.llm.manager import MockProvider
                return await MockProvider().generate_text(prompt, system_prompt, temperature)
            raise ValueError("GROQ_API_KEY is not configured.")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        # 1. Try primary model
        try:
            return await self._execute_request(self.model, messages, temperature=temperature)
        except Exception as exc:
            logger.warning(f"Primary Groq model {self.model} failed: {exc}. Trying fallback {self.fallback_model}...")

        # 2. Try fallback model
        try:
            return await self._execute_request(self.fallback_model, messages, temperature=temperature)
        except Exception as exc2:
            logger.error(f"Fallback Groq model {self.fallback_model} also failed: {exc2}")
            # If Gemini key exists, try Gemini
            if settings.GEMINI_API_KEY:
                from backend.app.infrastructure.llm.gemini import GeminiProvider
                logger.info("Attempting Gemini fallback after Groq exhaustion...")
                return await GeminiProvider().generate_text(prompt, system_prompt, temperature)
            raise

    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str,
        response_model: Type[T],
        temperature: float = 0.2
    ) -> T:
        if not self.api_key:
            if settings.ENVIRONMENT == "test":
                from backend.app.infrastructure.llm.manager import MockProvider
                return await MockProvider().generate_structured(prompt, system_prompt, response_model, temperature)
            raise ValueError("GROQ_API_KEY is not configured.")

        schema = json.dumps(response_model.model_json_schema(), indent=2)
        strict_system = (
            f"{system_prompt}\n\n"
            f"You are a strict JSON generator. Your output MUST be valid JSON adhering exactly to this schema:\n"
            f"{schema}\n"
            f"Do not output markdown code blocks, preambles, or conversational text. Output pure JSON."
        )

        messages = [
            {"role": "system", "content": strict_system},
            {"role": "user", "content": prompt}
        ]

        for attempt in range(1, 3):
            try:
                raw_text = await self._execute_request(
                    self.model,
                    messages,
                    temperature=temperature,
                    json_mode=True
                )
                cleaned = _extract_json_block(raw_text)
                parsed = json.loads(cleaned)
                return response_model.model_validate(parsed)
            except Exception as e:
                logger.warning(f"Groq structured generation attempt {attempt} failed ({self.model}): {e}")
                if attempt == 1 and self.fallback_model:
                    try:
                        raw_text = await self._execute_request(
                            self.fallback_model,
                            messages,
                            temperature=temperature,
                            json_mode=True
                        )
                        cleaned = _extract_json_block(raw_text)
                        return response_model.model_validate(json.loads(cleaned))
                    except Exception as fb_err:
                        logger.warning(f"Groq fallback model failed for structured output: {fb_err}")

        # Fallback to Gemini if configured
        if settings.GEMINI_API_KEY:
            logger.info("Falling back to Gemini for structured output...")
            from backend.app.infrastructure.llm.gemini import GeminiProvider
            return await GeminiProvider().generate_structured(prompt, system_prompt, response_model, temperature)

        raise ValueError(f"All Groq structured generation attempts failed for {response_model.__name__}.")

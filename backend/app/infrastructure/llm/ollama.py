import httpx
import json
from typing import Type, TypeVar
from pydantic import BaseModel
from backend.app.domain.llm_provider import LLMProvider

T = TypeVar('T', bound=BaseModel)

class OllamaProvider(LLMProvider):
    def __init__(self, host: str = "http://localhost:11434", model: str = "llama3"):
        self.host = host
        self.model = model

    async def generate_text(self, prompt: str, system_prompt: str, temperature: float = 0.2) -> str:
        url = f"{self.host}/api/chat"
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "options": {
                "temperature": temperature
            },
            "stream": False
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=body, timeout=60.0)
            if response.status_code == 200:
                res_json = response.json()
                return res_json["message"]["content"]
            else:
                raise ValueError(f"Ollama API failure: Status {response.status_code} - {response.text}")

    async def generate_structured(self, prompt: str, system_prompt: str, response_model: Type[T], temperature: float = 0.2) -> T:
        schema_json = json.dumps(response_model.model_json_schema())
        structured_system_prompt = (
            f"{system_prompt}\n\n"
            f"IMPORTANT: Your response must be a single, valid JSON object or array adhering strictly to this JSON Schema:\n"
            f"{schema_json}\n"
            f"Do NOT include markdown syntax (like ```json), commentary or formatting in your output."
        )

        response_text = await self.generate_text(prompt, structured_system_prompt, temperature)
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```json") or lines[0].startswith("```"):
                cleaned = "\n".join(lines[1:-1])
        cleaned = cleaned.strip()

        parsed_json = json.loads(cleaned)
        return response_model.model_validate(parsed_json)

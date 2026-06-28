from typing import Type, TypeVar
from pydantic import BaseModel
from backend.app.domain.llm_provider import LLMProvider
from backend.app.infrastructure.llm.gemini import GeminiProvider
from backend.app.infrastructure.llm.ollama import OllamaProvider
from backend.app.config import settings
import json

T = TypeVar('T', bound=BaseModel)

class MockProvider(LLMProvider):
    """
    Mock LLM provider that simulates responses for local offline verification.
    """
    async def generate_text(self, prompt: str, system_prompt: str, temperature: float = 0.2) -> str:
        return (
            "## Room-temperature Superconductivity Synthesis Report\n\n"
            "This report details current developments in LK-99 and sulfur hydride research, "
            "highlighting major reproducibility debates, structural details, and zero resistance studies.\n\n"
            "### 1. diamagnetism and impurities\n"
            "Synthesis experiments at multiple labs indicate copper sulfide impurities produce structural "
            "phase changes mimicking superconductivity. Zero-resistance has not been confirmed under standard pressures."
        )

    async def generate_structured(self, prompt: str, system_prompt: str, response_model: Type[T], temperature: float = 0.2) -> T:
        # Generate simulated schemas
        schema = response_model.model_json_schema()
        title = schema.get("title", "")
        
        # Determine target mock response based on class schema structure/title
        if "plan" in title.lower() or "Plan" in title:
            # Plan models
            data = {
                "plan": [
                    {"sub_query": f"Core diamagnetism claims in room-temperature superconductivity", "reason": "Analyze structural evidence of zero resistance claims."},
                    {"sub_query": f"SQUID and transport measurements on copper sulfide impurities", "reason": "Examine counter-arguments regarding phase transition impurities."}
                ]
            }
        elif "finding" in title.lower() or "claim" in title.lower() or "Finding" in title:
            data = {
                "claim": "Diamagnetic shielding transition in copper-doped lead apatite is induced by Cu2S phase transition rather than superconductivity.",
                "confidence_score": 92.5,
                "source_count": 4,
                "source_quality_score": 8.5,
                "verification_status": "VERIFIED",
                "consensus_rationale": "Independent tests confirm Cu2S impurities experience a structural transition at 370K, matching resistivity drops."
            }
        else:
            # Default empty initializer or try dictionary construction
            data = {}
            for name, prop in schema.get("properties", {}).items():
                if prop.get("type") == "string":
                    data[name] = "Mock String Output"
                elif prop.get("type") == "number":
                    data[name] = 80.0
                elif prop.get("type") == "integer":
                    data[name] = 3
                elif prop.get("type") == "array":
                    data[name] = []
        
        return response_model.model_validate(data)


class LLMManager:
    @staticmethod
    def get_provider(provider_name: str = "gemini") -> LLMProvider:
        """
        Pluggable provider resolver. Matches string identifiers to concrete classes.
        """
        p_name = provider_name.lower()
        if p_name == "gemini":
            if settings.GEMINI_API_KEY:
                return GeminiProvider()
            else:
                return MockProvider()
        elif p_name == "ollama":
            return OllamaProvider()
        
        # Default fallback
        return MockProvider()

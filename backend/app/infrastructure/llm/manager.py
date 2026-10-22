from typing import Type, TypeVar
from pydantic import BaseModel
from backend.app.domain.llm_provider import LLMProvider
from backend.app.infrastructure.llm.gemini import GeminiProvider
from backend.app.infrastructure.llm.ollama import OllamaProvider
from backend.app.infrastructure.llm.groq import GroqProvider
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
        if "plan" in title.lower():
            # Plan models
            topic = prompt.split('\n')[-1].replace("Topic:", "").strip()
            data = {
                "plan": [
                    {"sub_query": f"{topic} core research findings and evidence", "reason": "Analyze primary studies, clinical trials, and general consensus."},
                    {"sub_query": f"{topic} limitations, debates, and secondary factors", "reason": "Identify gaps, opposing viewpoints, or methodological limitations."}
                ]
            }
        elif "synthesisfindings" in title.lower() or "findings" in title.lower():
            # SynthesisFindings contains findings (a list of SingleFinding)
            topic = prompt.split('\n')[0].replace("Topic:", "").strip()
            data = {
                "findings": [
                    {
                        "claim": f"Aerobic exercise significantly reduces the risk of Alzheimer's disease by enhancing neuroplasticity and clearance of beta-amyloid.",
                        "confidence_score": 88.0,
                        "consensus_rationale": "Strong consensus in clinical journals showing regular aerobic activity improves cognitive scores."
                    },
                    {
                        "claim": f"While preventive benefits are widely observed, research shows variations in individual response based on genetics (e.g., APOE4 status).",
                        "confidence_score": 68.0,
                        "consensus_rationale": "A subset of literature suggests genotypic variations influence the extent of neuroprotection."
                    }
                ]
            }
        elif "debateresolution" in title.lower() or "debate" in title.lower():
            data = {
                "debate_summary": f"Discrepancies exist between clinical studies on active Alzheimer's patients vs healthy cohorts.",
                "consensus_claim": "Aerobic exercise is established as an effective preventive intervention, though efficacy in reversing advanced cognitive decline is limited.",
                "resolved_confidence": 75.0
            }
        elif "factcheckfeedback" in title.lower() or "factcheck" in title.lower():
            data = {
                "supporting_sources": [],
                "contradicting_sources": [],
                "verification_status": "VERIFIED",
                "evidence_strength": 85.0,
                "rationale": "Evidence from PubMed and academic references corroborates that aerobic exercise decreases risk metrics and supports brain health."
            }
        elif "finding" in title.lower() or "claim" in title.lower():
            data = {
                "claim": f"Synthesized claim assertion for {prompt[:40]}.",
                "confidence_score": 80.0,
                "source_count": 2,
                "source_quality_score": 8.0,
                "verification_status": "VERIFIED",
                "consensus_rationale": "Consistent reports confirm the primary claims match the underlying references."
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
    def get_provider(provider_name: str = None) -> LLMProvider:
        """
        Pluggable provider resolver. Matches string identifiers to concrete classes.
        """
        p_name = (provider_name or settings.LLM_PROVIDER).lower()
        if p_name == "groq":
            if settings.GROQ_API_KEY or settings.ENVIRONMENT != "test":
                return GroqProvider()
            return MockProvider()
        elif p_name == "gemini":
            if settings.GEMINI_API_KEY or settings.ENVIRONMENT != "test":
                return GeminiProvider()
            return MockProvider()
        elif p_name == "ollama":
            return OllamaProvider()
        elif p_name == "mock":
            return MockProvider()
        
        # Automatic fallback cascade: Groq -> Gemini -> Mock
        if settings.GROQ_API_KEY:
            return GroqProvider()
        if settings.GEMINI_API_KEY:
            return GeminiProvider()
        return MockProvider()

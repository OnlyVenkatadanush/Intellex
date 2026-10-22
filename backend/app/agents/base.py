import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import httpx
from backend.app.config import settings


class AgentState(BaseModel):
    session_id: str
    user_id: Optional[str] = None  # The authenticated user who owns this session
    query: str
    plan: List[Dict[str, Any]] = []
    evidence: List[Dict[str, Any]] = []
    findings: List[Dict[str, Any]] = []
    debates: List[Dict[str, Any]] = []
    consensus: Optional[str] = None
    confidence_score: float = 0.0
    report_markdown: Optional[str] = None
    citations: List[Dict[str, Any]] = []
    logs: List[Dict[str, Any]] = []


class Agent:
    def __init__(self, name: str, role: str, system_prompt: str):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt

    async def call_llm(self, prompt: str, schema_format: Optional[str] = None) -> str:
        """
        Executes text generation using LLMManager with fallback-resilient Gemini provider.
        """
        from backend.app.infrastructure.llm.manager import LLMManager
        try:
            provider = LLMManager.get_provider()
            return await provider.generate_text(prompt=prompt, system_prompt=self.system_prompt)
        except Exception as e:
            if settings.ENVIRONMENT == "test":
                return self._generate_mock_response(prompt, schema_format)
            raise RuntimeError(f"Agent {self.name} failed to generate LLM response: {e}") from e

    def _generate_mock_response(self, prompt: str, schema_format: Optional[str]) -> str:
        """
        Generates simulated expert outputs based on the agent's role and requested schema.
        Ensures execution finishes correctly without any credentials.
        """
        if schema_format == "json_plan":
            return json.dumps([
                {
                    "sub_query": f"Core analysis of {prompt[:40]}",
                    "reason": "Identify definition and fundamental components of the research topic."
                },
                {
                    "sub_query": f"Controversies, limitations and future developments in {prompt[:40]}",
                    "reason": "Examine counter-arguments, debates, and challenges in the domain."
                }
            ])
        elif schema_format == "json_findings":
            return json.dumps([
                {
                    "claim": f"Core consensus states that {prompt[:50]} represents a pivotal innovation in the field.",
                    "confidence_score": 85.0,
                    "consensus_rationale": "High agreement across literature sources regarding its structural foundation."
                },
                {
                    "claim": f"Minor controversies exist regarding efficiency boundaries and scalability limitations.",
                    "confidence_score": 65.0,
                    "consensus_rationale": "Different research teams report conflicting performance benchmarks."
                }
            ])
        elif schema_format == "json_debate":
            return json.dumps({
                "debate_summary": "Initial conflict detected on performance metrics across independent research groups.",
                "consensus_claim": "The consensus is that efficiency exceeds 80% under standard deployment profiles.",
                "resolved_confidence": 78.5
            })
        elif schema_format == "json_factcheck":
            return json.dumps({
                "verdict": "Verified with limitations",
                "score": 82.0,
                "confidence_rationale": "Most claims align with retrieved articles, though statistics are slightly generalized."
            })

        # Default text generator fallback
        return (
            f"### Research Report Synthesis on {prompt[:100]}\n\n"
            f"This is a synthesized mock analysis produced by the {self.name} Agent "
            f"because no external API keys were provided. It outlines structural patterns, "
            f"evidence collection, and verification results for: {prompt}.\n\n"
            f"- **Key Assertions**: Multi-agent operations require strong consensus algorithms.\n"
            f"- **Resolution**: Debates resolved successfully with 80% confidence scoring."
        )

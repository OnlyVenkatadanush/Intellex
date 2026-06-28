import logging
from pydantic import BaseModel, Field
from typing import List
from backend.app.agents.base import Agent, AgentState
from backend.app.infrastructure.llm.manager import LLMManager

logger = logging.getLogger(__name__)


class FactCheckFeedback(BaseModel):
    verification_status: str = Field(..., description="Status of verification: VERIFIED, CONTRADICTED, or INSUFFICIENT_EVIDENCE.")
    adjusted_confidence: float = Field(..., description="Adjusted confidence score between 0 and 100.")
    rationale: str = Field(..., description="Fact-check audit explanation.")

class FactCheckerAgent(Agent):
    def __init__(self):
        super().__init__(
            name="Fact Checker",
            role="Factual Verification Auditor",
            system_prompt=(
                "You are the Fact Checker Agent of Intellex.\n"
                "Audit synthesized claims against the retrieved evidence sources.\n"
                "Determine the verification status, adjust confidence, and provide audits."
            )
        )

    def _calculate_source_quality(self, source_name: str) -> float:
        """Assigns source authority values (0.0 - 10.0)."""
        name = source_name.lower()
        if "pubmed" in name:
            return 9.5
        elif "arxiv" in name:
            return 9.0
        elif "crossref" in name:
            return 9.0
        elif "user file" in name:
            return 8.5
        elif "wikipedia" in name:
            return 7.5
        
        # General Web Search
        return 7.0

    async def execute(self, state: AgentState) -> AgentState:
        state.logs.append({
            "agent_name": self.name,
            "agent_role": self.role,
            "message": "Auditing claims against retrieved source indices...",
            "log_type": "INFO"
        })

        llm = LLMManager.get_provider("gemini")
        evidence_context = "\n".join([
            f"Source ID {idx}: {item['source']} - Content: {item['content'][:250]}"
            for idx, item in enumerate(state.evidence)
        ])

        verified_findings = []
        for idx, finding in enumerate(state.findings):
            claim = finding.get("claim", "")
            prompt = f"Claim: {claim}\n\nEvidence Context:\n{evidence_context}\n\nAudit this claim."
            
            try:
                audit = await llm.generate_structured(
                    prompt=prompt,
                    system_prompt=self.system_prompt,
                    response_model=FactCheckFeedback
                )
                
                # Check source supporting indicators
                matching_sources = []
                for src in state.evidence:
                    words = [w for w in claim.lower().split() if len(w) > 5]
                    matches = sum(1 for w in words if w in src.get("content", "").lower() or w in src.get("title", "").lower())
                    if matches >= 2:
                        matching_sources.append(src)

                source_count = len(matching_sources)
                
                # Compute source quality
                if source_count > 0:
                    quality_score = sum(self._calculate_source_quality(s["source"]) for s in matching_sources) / source_count
                    status = audit.verification_status
                    confidence = audit.adjusted_confidence
                else:
                    # Strict Integrity rule: 0 sources = Insufficient Evidence!
                    source_count = 0
                    quality_score = 0.0
                    status = "INSUFFICIENT_EVIDENCE"
                    confidence = 0.0
                    claim = f"[Insufficient Evidence] {claim}"

                verified_findings.append({
                    "id": finding.get("id", str(idx + 1)),
                    "claim": claim,
                    "confidence_score": confidence,
                    "source_count": source_count,
                    "source_quality_score": round(quality_score, 2),
                    "verification_status": status,
                    "consensus_rationale": audit.rationale,
                    "matching_sources": matching_sources
                })
            except Exception as exc:
                # CRITICAL INTEGRITY FIX: Never fallback to VERIFIED status.
                # An LLM audit failure means we cannot confirm the claim.
                # Use INSUFFICIENT_EVIDENCE with a conservative confidence.
                logger.warning(f"FactChecker LLM audit failed for finding {idx}: {exc}")
                verified_findings.append({
                    "id": finding.get("id", str(idx + 1)),
                    "claim": claim,
                    "confidence_score": min(float(finding.get("confidence_score", 50.0)), 50.0),
                    "source_count": len([s for s in state.evidence
                                         if any(w in s.get("content", "").lower()
                                                for w in claim.lower().split() if len(w) > 5)][:3]),
                    "source_quality_score": 5.0,
                    "verification_status": "INSUFFICIENT_EVIDENCE",
                    "consensus_rationale": "Verification audit could not be completed due to a system error. Treat with caution.",
                    "matching_sources": state.evidence[:1]
                })


        state.findings = verified_findings
        return state


class CitationAgent(Agent):
    def __init__(self, citation_format: str = "APA"):
        super().__init__(
            name="Citation Broker",
            role="Reference Indexer",
            system_prompt="You build standard bibliography listings."
        )
        self.citation_format = citation_format

    def _format_citation(self, title: str, url: str, source: str) -> str:
        """Formats the reference matching IEEE or APA standards."""
        clean_title = title.strip().replace("\n", " ")
        if self.citation_format == "IEEE":
            return f'"{clean_title}," {source}. Available: {url or "N/A"}.'
        
        # APA
        return f'{clean_title}. ({source}). Retrieved from {url or "N/A"}.'

    async def execute(self, state: AgentState) -> AgentState:
        state.logs.append({
            "agent_name": self.name,
            "agent_role": self.role,
            "message": f"Mapping reference citations using {self.citation_format} standards...",
            "log_type": "INFO"
        })

        citations = []
        for finding in state.findings:
            matching_sources = finding.get("matching_sources", [])
            finding_citations = []
            
            for src in matching_sources[:2]: # Max 2 citations per claim
                cit_id = f"REF-{len(citations) + 1}"
                formatted = self._format_citation(
                    title=src.get("title", "Unknown Source"),
                    url=src.get("url", ""),
                    source=src.get("source", "Web")
                )
                
                citation_record = {
                    "id": cit_id,
                    "finding_id": finding.get("id"),
                    "source_title": formatted,
                    "source_url": src.get("url"),
                    "citation_format": self.citation_format,
                    "quote": src.get("content")[:200]
                }
                citations.append(citation_record)
                finding_citations.append(citation_record)
            
            # Save mapped citation records on finding
            finding["citations"] = finding_citations

        state.citations = citations
        return state

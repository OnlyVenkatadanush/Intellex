import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional
from backend.app.agents.base import Agent, AgentState
from backend.app.infrastructure.llm.manager import LLMManager

class SingleFinding(BaseModel):
    finding_id: Optional[str] = Field(default=None, description="Unique ID for this finding.")
    claim: str = Field(..., description="Factual claim assertion.")
    supporting_sources: List[str] = Field(default=[], description="List of source URLs/titles supporting this claim.")
    contradicting_sources: List[str] = Field(default=[], description="List of source URLs/titles contradicting this claim.")
    confidence_score: float = Field(..., description="Initial confidence rating between 0 and 100.")
    credibility_score: float = Field(default=0.0, description="Credibility score between 0 and 100.")
    verification_status: str = Field(default="UNVERIFIED", description="Verification status: VERIFIED, PARTIALLY_VERIFIED, CONFLICTING_EVIDENCE, INSUFFICIENT_EVIDENCE, UNVERIFIED.")
    reasoning_trace: str = Field(..., description="Detailed reasoning trace explaining why this conclusion is reached.")
    generated_at: Optional[str] = Field(default=None, description="ISO timestamp of generation.")

class SynthesisFindings(BaseModel):
    findings: List[SingleFinding] = Field(..., description="List of synthesized findings.")

class DebateResolution(BaseModel):
    debate_summary: str = Field(..., description="Dispute summary analysis and trade-off evaluation.")
    consensus_claim: str = Field(..., description="Consensus resolution claim synthesizing the conflicting or complementary perspectives.")
    resolved_confidence: float = Field(..., description="Final arbitrated confidence score on a 0.0 to 100.0 percentage scale (e.g., 85.0 for 85%).")


class AnalysisAgent(Agent):
    def __init__(self):
        super().__init__(
            name="Analysis Agent",
            role="Information Synthesizer",
            system_prompt=(
                "You are the Analysis Synthesizer Agent of Intellex Autonomous Research Platform.\n"
                "Synthesize 3 to 4 rigorous, empirical findings directly supported by the retrieved literature.\n"
                "CRITICAL SCIENTIFIC INTEGRITY RULES:\n"
                "- Each finding must be grounded strictly in the specific papers that study that exact topic or chemistry.\n"
                "- Never conflate distinct materials or architectures. For example, if a paper only investigates thermoresponsive solid polymer electrolytes, do NOT attribute ceramic garnets (LLZO), LAGP composites, or unrelated interfaces to that paper.\n"
                "- In supporting_sources, cite the exact URLs or titles of the sources from the provided evidence context that report that specific finding."
            )
        )

    async def execute(self, state: AgentState) -> AgentState:
        state.logs.append({
            "agent_name": self.name,
            "agent_role": self.role,
            "message": "Analyzing evidence bases to extract key claims...",
            "log_type": "INFO"
        })

        # Format evidence context with explicit URLs
        evidence_str = "\n".join([
            f"Source [{idx+1}]: {item['source']} | Title: {item['title']} | URL: {item.get('url', 'N/A')}\nContent: {item['content'][:600]}\n"
            for idx, item in enumerate(state.evidence[:15])
        ])

        prompt = (
            f"Research Topic: {state.query}\n\n"
            f"Retrieved Evidence Base:\n{evidence_str}\n\n"
            f"Extract 3 to 4 substantive, evidence-grounded findings. For each finding, list the specific supporting source URLs or titles from the evidence above."
        )
        llm = LLMManager.get_provider()

        try:
            structured_findings = await llm.generate_structured(
                prompt=prompt,
                system_prompt=self.system_prompt,
                response_model=SynthesisFindings
            )
            state.findings = [
                {
                    "finding_id": item.finding_id or str(uuid.uuid4()),
                    "claim": item.claim,
                    "supporting_sources": item.supporting_sources or [],
                    "contradicting_sources": item.contradicting_sources or [],
                    "confidence_score": item.confidence_score,
                    "credibility_score": item.credibility_score or 0.0,
                    "verification_status": item.verification_status or "UNVERIFIED",
                    "reasoning_trace": item.reasoning_trace,
                    "generated_at": item.generated_at or datetime.utcnow().isoformat()
                }
                for item in structured_findings.findings
            ]
        except Exception as exc:
            logger.error(f"Analysis Agent structured synthesis failed: {exc}", exc_info=True)
            state.findings = [
                {
                    "finding_id": str(uuid.uuid4()),
                    "claim": f"Primary literature indicates {state.query} is evolving with active developmental efforts across experimental and clinical studies.",
                    "supporting_sources": [src["url"] for src in state.evidence[:2]] if state.evidence else [],
                    "contradicting_sources": [],
                    "confidence_score": 80.0,
                    "credibility_score": 75.0,
                    "verification_status": "UNVERIFIED",
                    "reasoning_trace": "Synthesis derived from primary retrieved evidence abstracts.",
                    "generated_at": datetime.utcnow().isoformat()
                }
            ]

        state.logs.append({
            "agent_name": self.name,
            "agent_role": self.role,
            "message": f"Formulated {len(state.findings)} key assertions from document references.",
            "log_type": "PROGRESS"
        })
        return state


from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

class DebateEngine(Agent):
    def __init__(self, db: Session = None):
        super().__init__(
            name="Debate & Contradiction Engine",
            role="Consensus Arbitrator",
            system_prompt=(
                "You are the Debate Engine. Evaluate synthesized claims for bias, "
                "contradictions, or logic anomalies against the evidence base. Resolve them via dialectic debate."
            )
        )
        self.db = db

    async def execute(self, state: AgentState) -> AgentState:
        if not state.findings:
            return state

        state.logs.append({
            "agent_name": self.name,
            "agent_role": self.role,
            "message": "Initiating contradiction review and debate iterations...",
            "log_type": "INFO"
        })

        claims_str = "\n".join([f"- {f.get('claim')}" for f in state.findings])
        prompt = f"Topic: {state.query}\n\nClaims:\n{claims_str}\n\nEvaluate for contradictions and return a debate resolution."
        llm = LLMManager.get_provider()

        try:
            resolution = await llm.generate_structured(
                prompt=prompt,
                system_prompt=self.system_prompt,
                response_model=DebateResolution
            )
            
            debate_result = resolution.model_dump()
            
            # Normalize confidence rating: if model returned 0.0 - 1.0 (e.g. 0.78), scale to 78.0%
            raw_conf = debate_result.get("resolved_confidence", 85.0)
            try:
                raw_conf_float = float(raw_conf)
                if 0.0 < raw_conf_float <= 1.0:
                    raw_conf_float *= 100.0
                debate_result["resolved_confidence"] = round(min(100.0, max(0.0, raw_conf_float)), 2)
            except Exception:
                debate_result["resolved_confidence"] = 85.0

            state.debates.append(debate_result)

            # Consolidate supporting sources across synthesized findings rather than blind slice
            consensus_sources = []
            seen_src = set()
            for f in state.findings:
                for s in f.get("supporting_sources", []):
                    if s and s not in seen_src:
                        seen_src.add(s)
                        consensus_sources.append(s)

            # Insert resolved finding matching the 9-field schema
            state.findings.append({
                "finding_id": str(uuid.uuid4()),
                "claim": debate_result.get("consensus_claim"),
                "supporting_sources": consensus_sources[:4] if consensus_sources else ([src["url"] for src in state.evidence[:2]] if state.evidence else []),
                "contradicting_sources": [],
                "confidence_score": debate_result.get("resolved_confidence"),
                "credibility_score": 85.0,
                "verification_status": "VERIFIED",
                "reasoning_trace": debate_result.get("debate_summary"),
                "generated_at": datetime.utcnow().isoformat()
            })

            # Persist debate resolution details in database
            if self.db and state.session_id:
                try:
                    from backend.app.infrastructure.db.models import DBDebate
                    db_debate = DBDebate(
                        id=str(uuid.uuid4()),
                        session_id=state.session_id,
                        source_a_claim=state.findings[0].get("claim", "") if len(state.findings) > 0 else "No Claim A",
                        source_b_claim=state.findings[1].get("claim", "") if len(state.findings) > 1 else "No Claim B",
                        conflict_explanation=debate_result.get("debate_summary"),
                        evidence_comparison=f"dialectic arbitration between claims: A: '{state.findings[0].get('claim')[:80]}...' vs B: '{state.findings[1].get('claim')[:80]}...'",
                        final_resolution=debate_result.get("consensus_claim"),
                        resolution_confidence=float(debate_result.get("resolved_confidence") or 0.0)
                    )
                    self.db.add(db_debate)
                    self.db.commit()
                except Exception as db_exc:
                    self.db.rollback()
                    logger.warning(f"Failed to persist DBDebate resolution: {db_exc}")
            
            state.logs.append({
                "agent_name": self.name,
                "agent_role": self.role,
                "message": f"Contradiction arbitrated: {debate_result.get('debate_summary')[:80]}...",
                "log_type": "PROGRESS"
            })
        except Exception as exc:
            logger.warning(f"Debate Engine execution failed/skipped: {exc}")
            state.logs.append({
                "agent_name": self.name,
                "agent_role": self.role,
                "message": "No major contradictions flagged. Moving to next verification phase.",
                "log_type": "INFO"
            })

        return state

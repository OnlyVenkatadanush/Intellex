from typing import List
from pydantic import BaseModel, Field
from backend.app.agents.base import Agent, AgentState
from backend.app.infrastructure.llm.manager import LLMManager

class SubQueryPlan(BaseModel):
    sub_query: str = Field(..., description="A precise search query or investigation target.")
    reason: str = Field(..., description="Detailed rationale for this query.")

class ResearchPlan(BaseModel):
    plan: List[SubQueryPlan] = Field(..., description="Array of investigation sub-queries.")

class CROAgent(Agent):
    def __init__(self):
        super().__init__(
            name="Chief Research Officer",
            role="Research Planner & Coordinator",
            system_prompt=(
                "You are the Chief Research Officer of Intellex Autonomous Research Platform.\n"
                "Decompose the user's research topic into a rigorous plan of 3 distinct, highly targeted sub-queries:\n"
                "1. Fundamental mechanisms, primary empirical evidence, and current scientific consensus.\n"
                "2. Known contradictions, methodological limitations, risks, and opposing viewpoints in the literature.\n"
                "3. Emerging breakthroughs, recent benchmarks, and future translation/scalability prospects.\n"
                "Ensure each sub-query is precise, searchable, and accompanied by a detailed strategic rationale."
            )
        )

    async def execute(self, state: AgentState) -> AgentState:
        llm = LLMManager.get_provider()
        prompt = f"Decompose this research topic into an executable plan of 3 distinct investigation sub-queries:\n\n{state.query}"
        
        try:
            structured_plan = await llm.generate_structured(
                prompt=prompt,
                system_prompt=self.system_prompt,
                response_model=ResearchPlan
            )
            state.plan = [item.model_dump() for item in structured_plan.plan]
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"CRO structured planning encountered error: {e}")
            state.plan = [
                {"sub_query": f"{state.query} empirical evidence mechanisms", "reason": "Establish baseline consensus and verified findings."},
                {"sub_query": f"{state.query} limitations debates contradictions", "reason": "Examine counter-arguments, failure modes, and conflicting literature."},
                {"sub_query": f"{state.query} emerging breakthroughs recent developments", "reason": "Evaluate state-of-the-art advances and future trajectories."}
            ]
        
        state.logs.append({
            "agent_name": self.name,
            "agent_role": self.role,
            "message": f"Planned research execution path with {len(state.plan)} investigation steps.",
            "log_type": "INFO"
        })
        return state

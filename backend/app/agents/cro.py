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
                "You are the Chief Research Officer of Intellex.\n"
                "Decompose the user's research topic into a plan of 2 to 3 distinct sub-queries.\n"
                "Specify a clear query and rationalization for each step."
            )
        )

    async def execute(self, state: AgentState) -> AgentState:
        # Use pluggable LLM Manager
        llm = LLMManager.get_provider("gemini")
        
        prompt = f"Decompose this research topic into an executable plan of sub-queries:\n\n{state.query}"
        
        try:
            # Generate structured response using the Pydantic schema
            structured_plan = await llm.generate_structured(
                prompt=prompt,
                system_prompt=self.system_prompt,
                response_model=ResearchPlan
            )
            state.plan = [item.model_dump() for item in structured_plan.plan]
        except Exception as e:
            # Safe fallback if LLM schema fails
            state.plan = [
                {"sub_query": f"{state.query} overview", "reason": "Establish baseline definitions."},
                {"sub_query": f"{state.query} analysis", "reason": "Analyze structural details and controversies."}
            ]
        
        state.logs.append({
            "agent_name": self.name,
            "agent_role": self.role,
            "message": f"Planned research execution path with {len(state.plan)} investigation steps.",
            "log_type": "INFO"
        })
        return state

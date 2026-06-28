from backend.app.agents.base import Agent, AgentState
from backend.app.infrastructure.db.models import DBMemory
from sqlalchemy.orm import Session
import uuid


class MemoryAgent(Agent):
    def __init__(self, db: Session = None):
        super().__init__(
            name="Memory Agent",
            role="Long-term Semantic Indexer",
            system_prompt="You save research findings into the platform's semantic memories database."
        )
        self.db = db

    async def execute(self, state: AgentState) -> AgentState:
        if not self.db or not state.findings:
            return state

        state.logs.append({
            "agent_name": self.name,
            "agent_role": self.role,
            "message": "Archiving verified research findings into long-term memory...",
            "log_type": "INFO"
        })

        saved_count = 0
        for finding in state.findings:
            # Only archive VERIFIED findings — do not pollute memory with unverified claims
            if finding.get("verification_status") == "VERIFIED":
                claim = finding.get("claim", "")
                if not claim:
                    continue

                # Use the actual session owner user_id from state
                # state.user_id is set by the ResearchManager before pipeline execution
                owner_id = getattr(state, "user_id", None) or state.session_id

                # Real embeddings would call Gemini text-embedding-004 here.
                # Using a deterministic zero-vector as placeholder until embedding
                # service is configured — the vector search fallback handles this gracefully.
                placeholder_embedding = [0.0] * 768

                try:
                    db_mem = DBMemory(
                        id=str(uuid.uuid4()),
                        user_id=owner_id,
                        content=claim,
                        embedding=placeholder_embedding
                    )
                    self.db.add(db_mem)
                    self.db.commit()
                    saved_count += 1
                except Exception as exc:
                    self.db.rollback()
                    state.logs.append({
                        "agent_name": self.name,
                        "agent_role": self.role,
                        "message": f"Warning: Failed to persist memory record — {str(exc)}",
                        "log_type": "WARNING"
                    })

        state.logs.append({
            "agent_name": self.name,
            "agent_role": self.role,
            "message": f"Archived {saved_count} verified findings into long-term memory.",
            "log_type": "INFO"
        })
        return state

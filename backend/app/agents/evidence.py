from backend.app.agents.base import Agent, AgentState
from backend.app.utils.search_tools import SearchTools
from backend.app.infrastructure.db.models import DBDocument
from sqlalchemy.orm import Session
from typing import List, Dict, Any

class EvidenceGatherer(Agent):
    def __init__(self, db: Session = None):
        super().__init__(
            name="Evidence Layer",
            role="Information Retrieval Agent",
            system_prompt="You coordinate evidence retrieval across external search engines, academic indexes, and local user files."
        )
        self.db = db

    async def execute(self, state: AgentState) -> AgentState:
        state.logs.append({
            "agent_name": self.name,
            "agent_role": self.role,
            "message": "Initializing multi-modal evidence collection...",
            "log_type": "INFO"
        })

        # 1. Fetch user-uploaded documents from DB for this session
        uploaded_docs = []
        if self.db and state.session_id:
            try:
                db_docs = self.db.query(DBDocument).filter(DBDocument.session_id == state.session_id).all()
                for doc in db_docs:
                    uploaded_docs.append({
                        "title": doc.filename,
                        "url": f"local://{doc.filename}",
                        "content": doc.extracted_text,
                        "source": f"User File ({doc.file_type})"
                    })
            except Exception:
                pass

        # 2. Iterate planned sub-queries
        for step in state.plan:
            sub_query = step.get("sub_query", state.query)
            
            # Fetch from APIs
            arxiv_papers = await SearchTools.fetch_arxiv_papers(sub_query, max_results=3)
            pubmed_papers = await SearchTools.fetch_pubmed_papers(sub_query, max_results=2)
            web_findings = await SearchTools.web_search(sub_query, max_results=3)
            
            # Check local documents matching keywords
            local_matches = []
            keywords = [w.lower() for w in sub_query.split() if len(w) > 4]
            for doc in uploaded_docs:
                match_count = sum(1 for kw in keywords if kw in doc["content"].lower())
                if match_count > 0:
                    local_matches.append(doc)

            combined = arxiv_papers + pubmed_papers + web_findings + local_matches
            
            for item in combined:
                item["query_target"] = sub_query
                state.evidence.append(item)
            
            state.logs.append({
                "agent_name": self.name,
                "agent_role": self.role,
                "message": f"Retrieved {len(combined)} reference sources (including {len(local_matches)} matching uploaded files) for target: '{sub_query}'",
                "log_type": "PROGRESS"
            })

        state.logs.append({
            "agent_name": self.name,
            "agent_role": self.role,
            "message": f"Ingestion completed. Accumulated total of {len(state.evidence)} sources.",
            "log_type": "INFO"
        })
        return state

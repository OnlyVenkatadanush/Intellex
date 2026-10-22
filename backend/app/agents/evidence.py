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
            
            # Fetch from live APIs
            arxiv_papers = await SearchTools.fetch_arxiv_papers(sub_query, max_results=3)
            pubmed_papers = await SearchTools.fetch_pubmed_papers(sub_query, max_results=3)
            crossref_papers = await SearchTools.fetch_crossref_papers(sub_query, max_results=3)
            web_findings = await SearchTools.web_search(sub_query, max_results=3)
            
            # Check local documents matching keywords
            local_matches = []
            keywords = [w.lower() for w in sub_query.split() if len(w) > 4]
            for doc in uploaded_docs:
                match_count = sum(1 for kw in keywords if kw in doc["content"].lower())
                if match_count > 0:
                    local_matches.append(doc)

            combined = arxiv_papers + pubmed_papers + crossref_papers + web_findings + local_matches
            
            # Robust Deduplication by canonical DOI, normalized URL, and Title
            import re
            existing_urls = {e.get("url").strip().rstrip("/").lower() for e in state.evidence if e.get("url")}
            existing_dois = {e.get("doi").strip().lower() for e in state.evidence if e.get("doi")}
            existing_titles = {e.get("title").strip().lower() for e in state.evidence if e.get("title")}
            
            unique_new = []
            for item in combined:
                url = item.get("url", "").strip()
                norm_url = url.rstrip("/").lower()
                doi = item.get("doi", "").strip()
                norm_doi = doi.lower() if doi else None
                title = item.get("title", "").strip().lower()

                # Reject any supplementary deposit files
                if re.search(r"\.(s\d+|supp\d*)$", norm_url) or (norm_doi and re.search(r"\.(s\d+|supp\d*)$", norm_doi)):
                    continue

                # Check if already seen
                if norm_doi and norm_doi in existing_dois:
                    continue
                if norm_url and norm_url in existing_urls:
                    continue
                if title and len(title) > 15 and title in existing_titles:
                    continue

                item["query_target"] = sub_query
                state.evidence.append(item)
                unique_new.append(item)

                if norm_url:
                    existing_urls.add(norm_url)
                if norm_doi:
                    existing_dois.add(norm_doi)
                if title:
                    existing_titles.add(title)
            
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

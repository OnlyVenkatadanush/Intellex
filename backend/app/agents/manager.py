import uuid
import json
import time
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from backend.app.agents.base import AgentState
from backend.app.agents.cro import CROAgent
from backend.app.agents.evidence import EvidenceGatherer
from backend.app.agents.reasoning import AnalysisAgent, DebateEngine
from backend.app.agents.quality import FactCheckerAgent, CitationAgent
from backend.app.agents.memory import MemoryAgent
from backend.app.agents.output import OutputAgent
from backend.app.agents.graph_builder import KnowledgeGraphBuilder
from backend.app.infrastructure.db.models import (
    DBExecutionLog, DBFinding, DBCitation, DBSession
)


logger = logging.getLogger(__name__)


class ResearchManager:
    def __init__(self, db: Session):
        self.db = db

    async def run_session(
        self,
        session_id: str,
        query: str,
        user_id: str,
        citation_format: str = "APA"
    ):
        """
        Executes the multi-agent pipeline sequentially, yielding log events for SSE streaming.
        Saves findings, citations, logs, and report markdown to the database.

        Fixes applied:
        - user_id is now passed into AgentState for correct memory attribution
        - citation_format is correctly forwarded to CitationAgent
        - Exception propagation: errors yield error events rather than silent pass
        - Proper DB transaction management with rollback on failure
        """
        # Initialize state with both session_id AND user_id
        state = AgentState(
            session_id=session_id,
            user_id=user_id,
            query=query
        )

        # Update session status to PLANNING
        db_sess = self.db.query(DBSession).filter(DBSession.id == session_id).first()
        if not db_sess:
            yield {"agent_name": "System", "agent_role": "Orchestrator",
                   "message": f"Session {session_id} not found.", "log_type": "ERROR"}
            return

        try:
            db_sess.status = "PLANNING"
            self.db.commit()

            # ── Step 1: Chief Research Officer Planning ──────────────────────
            cro = CROAgent()
            state, log = await self._run_step(cro, state)
            yield log

            # ── Step 2: Evidence Collection ──────────────────────────────────
            db_sess.status = "RESEARCHING"
            self.db.commit()
            gatherer = EvidenceGatherer(self.db)
            state, log = await self._run_step(gatherer, state)
            yield log

            # ── Step 3: Analysis Synthesizer ─────────────────────────────────
            analyzer = AnalysisAgent()
            state, log = await self._run_step(analyzer, state)
            yield log

            # ── Step 4: Contradiction & Debate ───────────────────────────────
            db_sess.status = "DEBATING"
            self.db.commit()
            debate = DebateEngine()
            state, log = await self._run_step(debate, state)
            yield log

            # ── Step 5: Fact Checking & Integrity Metrics ─────────────────────
            checker = FactCheckerAgent()
            state, log = await self._run_step(checker, state)
            yield log

            # ── Step 6: Citation Formatting (with correct format) ─────────────
            citer = CitationAgent(citation_format=citation_format)
            state, log = await self._run_step(citer, state)
            yield log

            # ── Step 7: Long-term Memory Indexing ────────────────────────────
            memorizer = MemoryAgent(self.db)
            state, _ = await self._run_step(memorizer, state)

            # ── Step 8: Report Assembly ───────────────────────────────────────
            assembler = OutputAgent()
            state, log = await self._run_step(assembler, state)
            yield log

            # ── Step 9: Knowledge Graph Construction ──────────────────────────────────
            try:
                graph_builder = KnowledgeGraphBuilder(self.db)
                graph_builder.build_graph(state)
            except Exception as graph_exc:
                logger.warning(f"Knowledge graph build failed (non-fatal): {graph_exc}")

            # ── Step 10: Persist all results to database ───────────────────────────────
            db_sess.status = "COMPLETED"
            db_sess.report_markdown = state.report_markdown
            self.db.commit()

            await self._persist_findings(state, session_id)

            yield {
                "agent_name": "System",
                "agent_role": "Orchestrator",
                "message": f"Research pipeline completed. {len(state.findings)} findings saved.",
                "log_type": "INFO"
            }

        except Exception as exc:
            # Propagate failure to the SSE stream instead of silent pass
            logger.error(f"Research pipeline failed for session {session_id}: {exc}", exc_info=True)
            try:
                db_sess.status = "FAILED"
                self.db.commit()
            except Exception:
                self.db.rollback()

            yield {
                "agent_name": "System",
                "agent_role": "Orchestrator",
                "message": f"Pipeline failed: {str(exc)}",
                "log_type": "ERROR"
            }

    async def _run_step(self, agent, state: AgentState):
        """
        Executes a single agent step, persists its logs, and returns
        the updated state plus the last log entry for SSE streaming.
        """
        start_time = time.monotonic()
        state = await agent.execute(state)
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # Write the most recent logs from this step to DB
        logs_to_write = state.logs[-3:]  # Capture last 3 logs (covers multi-log agents)
        for log in logs_to_write:
            try:
                db_log = DBExecutionLog(
                    id=str(uuid.uuid4()),
                    session_id=state.session_id,
                    agent_name=log.get("agent_name", agent.name),
                    agent_role=log.get("agent_role", agent.role),
                    message=log.get("message", ""),
                    log_type=log.get("log_type", "INFO")
                )
                self.db.add(db_log)
            except Exception as log_exc:
                logger.warning(f"Failed to persist log entry: {log_exc}")

        try:
            self.db.commit()
        except Exception as commit_exc:
            self.db.rollback()
            logger.warning(f"Log commit failed: {commit_exc}")

        # The last log entry is what gets streamed to the client
        last_log = state.logs[-1] if state.logs else {
            "agent_name": agent.name,
            "agent_role": agent.role,
            "message": f"Completed in {elapsed_ms}ms",
            "log_type": "INFO"
        }
        return state, last_log

    async def _persist_findings(self, state: AgentState, session_id: str):
        """
        Persists all verified findings and their citations to the database.
        Uses a single transaction per finding for atomicity.
        """
        for f in state.findings:
            try:
                finding_id = str(uuid.uuid4())
                db_finding = DBFinding(
                    id=finding_id,
                    session_id=session_id,
                    claim=f.get("claim", ""),
                    confidence_score=float(f.get("confidence_score", 0.0)),
                    source_count=int(f.get("source_count", 0)),
                    source_quality_score=float(f.get("source_quality_score", 0.0)),
                    verification_status=f.get("verification_status", "INSUFFICIENT_EVIDENCE"),
                    consensus_rationale=f.get("consensus_rationale")
                )
                self.db.add(db_finding)
                self.db.flush()  # Get the ID without full commit

                for cit in f.get("citations", []):
                    db_citation = DBCitation(
                        id=str(uuid.uuid4()),
                        finding_id=finding_id,
                        source_title=cit.get("source_title", "Unknown Source"),
                        source_url=cit.get("source_url"),
                        citation_format=cit.get("citation_format", "APA"),
                        quote=cit.get("quote", "")[:500] if cit.get("quote") else None
                    )
                    self.db.add(db_citation)

                self.db.commit()
            except Exception as exc:
                self.db.rollback()
                logger.error(f"Failed to persist finding: {exc}", exc_info=True)

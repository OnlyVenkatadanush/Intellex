"""
backend/app/agents/graph_builder.py

Knowledge Graph Builder Agent — Sprint 5: Knowledge Graph Engine

Converts the agent state (findings, evidence, debates) into a structured
knowledge graph of nodes and edges saved to the database.

Node types:
  - QUERY: The root research question
  - CONCEPT: Key concepts from the plan
  - SOURCE: External evidence sources (arXiv, PubMed, web)
  - FINDING: Verified/unverified claims
  - DEBATE: Contradiction resolution

Edge types:
  - DERIVED_FROM: Finding derived from source
  - SUPPORTS: Source/finding supports another finding
  - CONTRADICTS: Source/finding contradicts another
  - RELATED_TO: Conceptual relationship
  - CITES: Citation link
"""

import uuid
import logging
from sqlalchemy.orm import Session

from backend.app.agents.base import AgentState
from backend.app.infrastructure.db.graph_models import KnowledgeGraphNode, KnowledgeGraphEdge

logger = logging.getLogger(__name__)


class KnowledgeGraphBuilder:
    """
    Builds and persists a knowledge graph from completed agent state.
    Run after the main agent pipeline completes.
    """

    def __init__(self, db: Session):
        self.db = db

    def build_graph(self, state: AgentState) -> dict:
        """
        Build a complete knowledge graph from the agent state.
        Returns a dict of {nodes: [...], edges: [...]} for the API response.
        """
        nodes = []
        edges = []
        session_id = state.session_id

        try:
            # ── Root Query Node ───────────────────────────────────────────────
            query_node_id = str(uuid.uuid4())
            query_node = KnowledgeGraphNode(
                id=query_node_id,
                session_id=session_id,
                label=state.query[:200],
                node_type="QUERY",
                description="Root research question"
            )
            self.db.add(query_node)
            nodes.append({"id": query_node_id, "label": state.query[:80], "type": "QUERY"})

            # ── Concept Nodes (from plan) ──────────────────────────────────────
            concept_node_ids = []
            for step in state.plan:
                concept_id = str(uuid.uuid4())
                label = step.get("sub_query", "Research Sub-Query")[:200]
                concept_node = KnowledgeGraphNode(
                    id=concept_id,
                    session_id=session_id,
                    label=label,
                    node_type="CONCEPT",
                    description=step.get("reason", "")[:500]
                )
                self.db.add(concept_node)
                concept_node_ids.append(concept_id)
                nodes.append({"id": concept_id, "label": label[:60], "type": "CONCEPT"})

                # Edge: QUERY → CONCEPT
                edge = KnowledgeGraphEdge(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    source_node_id=query_node_id,
                    target_node_id=concept_id,
                    relationship_type="RELATED_TO",
                    weight=1.0
                )
                self.db.add(edge)
                edges.append({
                    "source": query_node_id,
                    "target": concept_id,
                    "type": "RELATED_TO"
                })

            # ── Source Nodes (from evidence — limited to top 10) ──────────────
            source_node_ids = []
            for src in state.evidence[:10]:
                src_id = str(uuid.uuid4())
                src_label = src.get("title", "Unknown Source")[:200]
                src_node = KnowledgeGraphNode(
                    id=src_id,
                    session_id=session_id,
                    label=src_label,
                    node_type="SOURCE",
                    description=src.get("content", "")[:500],
                    metadata_json={
                        "url": src.get("url"),
                        "source_type": src.get("source", "Web")
                    }
                )
                self.db.add(src_node)
                source_node_ids.append(src_id)
                nodes.append({
                    "id": src_id,
                    "label": src_label[:60],
                    "type": "SOURCE",
                    "url": src.get("url")
                })

            # ── Finding Nodes ─────────────────────────────────────────────────
            finding_node_ids = []
            for f in state.findings:
                f_id = str(uuid.uuid4())
                claim = f.get("claim", "")[:300]
                verification = f.get("verification_status", "INSUFFICIENT_EVIDENCE")
                confidence = float(f.get("confidence_score", 0.0)) / 100.0

                f_node = KnowledgeGraphNode(
                    id=f_id,
                    session_id=session_id,
                    label=claim,
                    node_type="FINDING",
                    confidence=confidence,
                    description=f.get("consensus_rationale", "")[:500],
                    metadata_json={"verification_status": verification}
                )
                self.db.add(f_node)
                finding_node_ids.append(f_id)
                nodes.append({
                    "id": f_id,
                    "label": claim[:80],
                    "type": "FINDING",
                    "confidence": confidence,
                    "verification": verification
                })

                # Edge: QUERY → FINDING (derived from)
                edge = KnowledgeGraphEdge(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    source_node_id=query_node_id,
                    target_node_id=f_id,
                    relationship_type="DERIVED_FROM",
                    weight=confidence
                )
                self.db.add(edge)
                edges.append({"source": query_node_id, "target": f_id, "type": "DERIVED_FROM"})

                # Edge: SOURCE → FINDING (support relationships)
                matching = f.get("matching_sources", [])
                for src_match in matching[:3]:
                    # Find the source node ID by matching URL
                    src_url = src_match.get("url", "")
                    for i, src in enumerate(state.evidence[:10]):
                        if src.get("url") == src_url and i < len(source_node_ids):
                            rel_type = "SUPPORTS" if verification == "VERIFIED" else "RELATED_TO"
                            support_edge = KnowledgeGraphEdge(
                                id=str(uuid.uuid4()),
                                session_id=session_id,
                                source_node_id=source_node_ids[i],
                                target_node_id=f_id,
                                relationship_type=rel_type,
                                weight=0.8
                            )
                            self.db.add(support_edge)
                            edges.append({
                                "source": source_node_ids[i],
                                "target": f_id,
                                "type": rel_type
                            })
                            break

            # ── Debate/Contradiction Edges ─────────────────────────────────────
            if state.debates and len(finding_node_ids) >= 2:
                for debate in state.debates:
                    if len(finding_node_ids) >= 2:
                        # Mark first two findings as CONTRADICTS (approximation)
                        contra_edge = KnowledgeGraphEdge(
                            id=str(uuid.uuid4()),
                            session_id=session_id,
                            source_node_id=finding_node_ids[0],
                            target_node_id=finding_node_ids[1],
                            relationship_type="CONTRADICTS",
                            weight=0.6
                        )
                        self.db.add(contra_edge)
                        edges.append({
                            "source": finding_node_ids[0],
                            "target": finding_node_ids[1],
                            "type": "CONTRADICTS"
                        })

            self.db.commit()
            logger.info(
                f"Knowledge graph built: session={session_id} "
                f"nodes={len(nodes)} edges={len(edges)}"
            )

        except Exception as exc:
            self.db.rollback()
            logger.error(f"Knowledge graph build failed: {exc}", exc_info=True)

        return {"nodes": nodes, "edges": edges, "session_id": session_id}

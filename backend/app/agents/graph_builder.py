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
            # ── Root Query Node (Topic) ───────────────────────────────────────
            query_node_id = str(uuid.uuid4())
            query_node = KnowledgeGraphNode(
                id=query_node_id,
                session_id=session_id,
                label=state.query[:200],
                node_type="Topic",
                description="Root research question"
            )
            self.db.add(query_node)
            nodes.append({"id": query_node_id, "label": state.query[:80], "type": "Topic"})

            # ── Concept Nodes (from plan) ──────────────────────────────────────
            concept_node_ids = []
            for step in state.plan:
                concept_id = str(uuid.uuid4())
                label = step.get("sub_query", "Research Sub-Query")[:200]
                concept_node = KnowledgeGraphNode(
                    id=concept_id,
                    session_id=session_id,
                    label=label,
                    node_type="Concept",
                    description=step.get("reason", "")[:500]
                )
                self.db.add(concept_node)
                concept_node_ids.append(concept_id)
                nodes.append({"id": concept_id, "label": label[:60], "type": "Concept"})

                # Edge: Topic → Concept
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
                    node_type="Source",
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
                    "type": "Source",
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
                    node_type="Finding",
                    confidence=confidence,
                    description=f.get("reasoning_trace", "")[:500],
                    metadata_json={
                        "verification_status": verification,
                        "credibility_score": float(f.get("credibility_score", 0.0)),
                        "evidence_strength": float(f.get("evidence_strength", 0.0)),
                        "cross_source_agreement": float(f.get("cross_source_agreement", 0.0)),
                        "recency_score": float(f.get("recency_score", 0.0)),
                        "contradiction_penalty": float(f.get("contradiction_penalty", 0.0))
                    }
                )
                self.db.add(f_node)
                finding_node_ids.append(f_id)
                nodes.append({
                    "id": f_id,
                    "label": claim[:80],
                    "type": "Finding",
                    "confidence": confidence,
                    "verification": verification
                })

                # Edge: Topic → Finding (derived from)
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

                # ── Citation Nodes & CITES Edges ──────────────────────────────
                for cit in f.get("citations", []):
                    cit_id = str(uuid.uuid4())
                    cit_node = KnowledgeGraphNode(
                        id=cit_id,
                        session_id=session_id,
                        label=cit.get("source_title", "APA Citation")[:200],
                        node_type="Citation",
                        description=cit.get("quote", "")[:500],
                        metadata_json={
                            "url": cit.get("source_url"),
                            "format": cit.get("citation_format"),
                            "authors": cit.get("authors"),
                            "year": cit.get("year"),
                            "journal": cit.get("journal"),
                            "doi": cit.get("doi")
                        }
                    )
                    self.db.add(cit_node)
                    nodes.append({
                        "id": cit_id,
                        "label": cit.get("source_title", "APA Citation")[:60],
                        "type": "Citation"
                    })

                    # Edge: Finding → Citation (CITES)
                    cites_edge = KnowledgeGraphEdge(
                        id=str(uuid.uuid4()),
                        session_id=session_id,
                        source_node_id=f_id,
                        target_node_id=cit_id,
                        relationship_type="CITES",
                        weight=1.0
                    )
                    self.db.add(cites_edge)
                    edges.append({"source": f_id, "target": cit_id, "type": "CITES"})

                # ── Source → Finding Edges (SUPPORTS / CONTRADICTS) ───────────
                supporting_urls = f.get("supporting_sources", [])
                contradicting_urls = f.get("contradicting_sources", [])

                # supporting links
                for s_url in supporting_urls:
                    for i, src in enumerate(state.evidence[:10]):
                        if src.get("url") == s_url and i < len(source_node_ids):
                            support_edge = KnowledgeGraphEdge(
                                id=str(uuid.uuid4()),
                                session_id=session_id,
                                source_node_id=source_node_ids[i],
                                target_node_id=f_id,
                                relationship_type="SUPPORTS",
                                weight=0.9
                            )
                            self.db.add(support_edge)
                            edges.append({
                                "source": source_node_ids[i],
                                "target": f_id,
                                "type": "SUPPORTS"
                            })

                # contradicting links
                for c_url in contradicting_urls:
                    for i, src in enumerate(state.evidence[:10]):
                        if src.get("url") == c_url and i < len(source_node_ids):
                            contra_edge = KnowledgeGraphEdge(
                                id=str(uuid.uuid4()),
                                session_id=session_id,
                                source_node_id=source_node_ids[i],
                                target_node_id=f_id,
                                relationship_type="CONTRADICTS",
                                weight=0.9
                            )
                            self.db.add(contra_edge)
                            edges.append({
                                "source": source_node_ids[i],
                                "target": f_id,
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

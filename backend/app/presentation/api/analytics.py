"""
backend/app/presentation/api/analytics.py

Advanced analytics endpoints — Sprints 5, 6, 7:
  - GET /api/sessions/{id}/graph        — Knowledge graph (Sprint 5)
  - GET /api/sessions/{id}/replay       — Replay timeline (Sprint 6)
  - GET /api/sessions/{id}/compare/{b}  — Session comparison (Sprint 7)
  - GET /api/sessions/{id}/memory       — Memory bank viewer
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.utils.auth_helpers import get_current_user
from backend.app.infrastructure.db.models import (
    DBUser as User, DBSession, DBFinding, DBExecutionLog
)
from backend.app.infrastructure.db.graph_models import KnowledgeGraphNode, KnowledgeGraphEdge
from backend.app.infrastructure.db.models import DBMemory

router = APIRouter(prefix="/api/sessions", tags=["analytics"])
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Sprint 5: Knowledge Graph Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{session_id}/graph")
async def get_knowledge_graph(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve the knowledge graph for a research session.
    Returns nodes and edges suitable for React Flow visualization.
    """
    db_session = _get_session_or_404(session_id, current_user.id, db)

    nodes = db.query(KnowledgeGraphNode).filter(
        KnowledgeGraphNode.session_id == session_id
    ).all()

    edges = db.query(KnowledgeGraphEdge).filter(
        KnowledgeGraphEdge.session_id == session_id
    ).all()

    if not nodes:
        # Graph hasn't been built yet — build it from findings on the fly
        findings = db.query(DBFinding).filter(DBFinding.session_id == session_id).all()

        # Simple ad-hoc graph from findings only
        adhoc_nodes = [
            {"id": "root", "label": db_session.original_query[:80], "type": "QUERY", "x": 0, "y": 0}
        ]
        adhoc_edges = []

        for i, f in enumerate(findings):
            node_id = f.id
            col = i % 3
            row = i // 3
            adhoc_nodes.append({
                "id": node_id,
                "label": f.claim[:80],
                "type": "FINDING",
                "confidence": float(f.confidence_score) / 100.0,
                "verification": f.verification_status,
                "x": (col - 1) * 250,
                "y": (row + 1) * 150
            })
            adhoc_edges.append({
                "id": f"e-root-{node_id}",
                "source": "root",
                "target": node_id,
                "type": "DERIVED_FROM"
            })

        return {
            "session_id": session_id,
            "status": "adhoc",  # Full graph builds after research completes
            "nodes": adhoc_nodes,
            "edges": adhoc_edges
        }

    # Serialize persisted graph with React Flow compatible structure
    serialized_nodes = []
    for n in nodes:
        serialized_nodes.append({
            "id": n.id,
            "label": n.label[:80],
            "type": n.node_type,
            "description": n.description,
            "confidence": n.confidence,
            "metadata": n.metadata_json,
            "created_at": n.created_at.isoformat() if n.created_at else None
        })

    serialized_edges = []
    for e in edges:
        serialized_edges.append({
            "id": e.id,
            "source": e.source_node_id,
            "target": e.target_node_id,
            "type": e.relationship_type,
            "weight": e.weight
        })

    return {
        "session_id": session_id,
        "status": "persisted",
        "nodes": serialized_nodes,
        "edges": serialized_edges
    }


# ─────────────────────────────────────────────────────────────────────────────
# Sprint 6: Research Replay Timeline
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{session_id}/replay")
async def get_replay_timeline(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve the complete agent execution timeline for replay.
    Returns chronological log events with agent metadata.
    """
    _get_session_or_404(session_id, current_user.id, db)

    logs = (
        db.query(DBExecutionLog)
        .filter(DBExecutionLog.session_id == session_id)
        .order_by(DBExecutionLog.created_at.asc())
        .all()
    )

    # Group logs by agent step
    steps = []
    current_step = None

    for log in logs:
        agent_key = log.agent_name
        if current_step is None or current_step["agent_name"] != agent_key:
            current_step = {
                "step_index": len(steps) + 1,
                "agent_name": log.agent_name,
                "agent_role": log.agent_role,
                "started_at": log.created_at.isoformat() if log.created_at else None,
                "events": []
            }
            steps.append(current_step)

        current_step["events"].append({
            "id": log.id,
            "message": log.message,
            "log_type": log.log_type,
            "timestamp": log.created_at.isoformat() if log.created_at else None
        })

    return {
        "session_id": session_id,
        "total_steps": len(steps),
        "total_events": len(logs),
        "timeline": steps
    }


# ─────────────────────────────────────────────────────────────────────────────
# Sprint 7: Session Comparison
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{session_id}/compare/{other_session_id}")
async def compare_sessions(
    session_id: str,
    other_session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Compare two research sessions to identify:
    - New claims in session B not in session A
    - Removed claims from session A not in session B
    - Claims with changed confidence scores
    - Changes in verification status
    """
    session_a = _get_session_or_404(session_id, current_user.id, db)
    session_b = _get_session_or_404(other_session_id, current_user.id, db)

    findings_a = db.query(DBFinding).filter(DBFinding.session_id == session_id).all()
    findings_b = db.query(DBFinding).filter(DBFinding.session_id == other_session_id).all()

    # Simple text-similarity comparison using normalized claim text
    def normalize(text: str) -> str:
        return " ".join(text.lower().split()[:20])  # First 20 words as key

    claims_a = {normalize(f.claim): f for f in findings_a}
    claims_b = {normalize(f.claim): f for f in findings_b}

    new_claims = []
    for key, f in claims_b.items():
        if key not in claims_a:
            new_claims.append({
                "claim": f.claim,
                "confidence": float(f.confidence_score),
                "verification": f.verification_status
            })

    removed_claims = []
    for key, f in claims_a.items():
        if key not in claims_b:
            removed_claims.append({
                "claim": f.claim,
                "confidence": float(f.confidence_score),
                "verification": f.verification_status
            })

    confidence_changes = []
    for key in set(claims_a.keys()) & set(claims_b.keys()):
        fa = claims_a[key]
        fb = claims_b[key]
        delta = float(fb.confidence_score) - float(fa.confidence_score)
        if abs(delta) >= 5.0 or fa.verification_status != fb.verification_status:
            confidence_changes.append({
                "claim": fa.claim,
                "session_a_confidence": float(fa.confidence_score),
                "session_b_confidence": float(fb.confidence_score),
                "delta": round(delta, 2),
                "session_a_status": fa.verification_status,
                "session_b_status": fb.verification_status
            })

    return {
        "session_a": {
            "id": session_id,
            "query": session_a.original_query,
            "finding_count": len(findings_a)
        },
        "session_b": {
            "id": other_session_id,
            "query": session_b.original_query,
            "finding_count": len(findings_b)
        },
        "new_claims": new_claims,
        "removed_claims": removed_claims,
        "confidence_changes": confidence_changes,
        "summary": {
            "total_new": len(new_claims),
            "total_removed": len(removed_claims),
            "total_changed": len(confidence_changes)
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# Memory Bank Viewer
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{session_id}/memory")
async def get_session_memory(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve verified findings stored in the user's long-term memory bank."""
    _get_session_or_404(session_id, current_user.id, db)

    memories = (
        db.query(DBMemory)
        .filter(DBMemory.user_id == current_user.id)
        .order_by(DBMemory.created_at.desc())
        .limit(50)
        .all()
    )

    return {
        "user_id": current_user.id,
        "memory_count": len(memories),
        "memories": [
            {
                "id": m.id,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in memories
        ]
    }


# ─────────────────────────────────────────────────────────────────────────────
# Shared Helper
# ─────────────────────────────────────────────────────────────────────────────

def _get_session_or_404(session_id: str, user_id: str, db: Session) -> DBSession:
    session = db.query(DBSession).filter(
        DBSession.id == session_id,
        DBSession.user_id == user_id
    ).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research session '{session_id}' not found."
        )
    return session

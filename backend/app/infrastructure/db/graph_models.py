"""
Knowledge Graph DB models — Sprint 5: Knowledge Graph Engine

Adds:
  - KnowledgeGraphNode: A concept, source, or finding extracted from a session
  - KnowledgeGraphEdge: A directed relationship between two nodes
"""

import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.database import Base


class KnowledgeGraphNode(Base):
    __tablename__ = "knowledge_graph_nodes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(String(500), nullable=False)           # Human-readable label
    node_type = Column(String(50), nullable=False)         # CONCEPT | SOURCE | FINDING | QUERY
    description = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)              # 0.0–1.0 for FINDING nodes
    metadata_json = Column(JSON, nullable=True)            # Extra attributes (URL, author, etc.)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    outgoing_edges = relationship(
        "KnowledgeGraphEdge",
        foreign_keys="KnowledgeGraphEdge.source_node_id",
        back_populates="source_node",
        cascade="all, delete-orphan"
    )
    incoming_edges = relationship(
        "KnowledgeGraphEdge",
        foreign_keys="KnowledgeGraphEdge.target_node_id",
        back_populates="target_node",
        cascade="all, delete-orphan"
    )


class KnowledgeGraphEdge(Base):
    __tablename__ = "knowledge_graph_edges"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    source_node_id = Column(String, ForeignKey("knowledge_graph_nodes.id", ondelete="CASCADE"), nullable=False)
    target_node_id = Column(String, ForeignKey("knowledge_graph_nodes.id", ondelete="CASCADE"), nullable=False)
    relationship_type = Column(String(100), nullable=False)  # SUPPORTS | CONTRADICTS | DERIVED_FROM | CITES | RELATED_TO
    weight = Column(Float, nullable=True, default=1.0)       # Edge weight / confidence
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    source_node = relationship(
        "KnowledgeGraphNode",
        foreign_keys=[source_node_id],
        back_populates="outgoing_edges"
    )
    target_node = relationship(
        "KnowledgeGraphNode",
        foreign_keys=[target_node_id],
        back_populates="incoming_edges"
    )

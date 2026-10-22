from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from backend.app.config import settings

# Adjust sqlite connection configuration if database is SQLite
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def run_migrations(bind_engine=None):
    if bind_engine is None:
        bind_engine = engine
    from sqlalchemy import inspect, text
    import logging
    _logger = logging.getLogger("intellex.database")
    inspector = inspect(bind_engine)
    
    try:
        # 1. Update findings table if exists
        if inspector.has_table("findings"):
            findings_cols = [c["name"] for c in inspector.get_columns("findings")]
            new_findings_cols = {
                "supporting_sources": "TEXT",
                "contradicting_sources": "TEXT",
                "credibility_score": "NUMERIC(5, 2)",
                "reasoning_trace": "TEXT",
                "evidence_strength": "NUMERIC(5, 2)",
                "cross_source_agreement": "NUMERIC(5, 2)",
                "recency_score": "NUMERIC(5, 2)",
                "contradiction_penalty": "NUMERIC(5, 2)"
            }
            with bind_engine.connect() as conn:
                for col_name, col_type in new_findings_cols.items():
                    if col_name not in findings_cols:
                        _logger.info(f"Migration: Adding column {col_name} to findings table")
                        conn.execute(text(f"ALTER TABLE findings ADD COLUMN {col_name} {col_type}"))
                conn.commit()
                
        # 2. Update citations table if exists
        if inspector.has_table("citations"):
            citations_cols = [c["name"] for c in inspector.get_columns("citations")]
            new_citations_cols = {
                "authors": "TEXT",
                "year": "VARCHAR(50)",
                "journal": "VARCHAR(255)",
                "doi": "VARCHAR(255)",
                "source_type": "VARCHAR(100)"
            }
            with bind_engine.connect() as conn:
                for col_name, col_type in new_citations_cols.items():
                    if col_name not in citations_cols:
                        _logger.info(f"Migration: Adding column {col_name} to citations table")
                        conn.execute(text(f"ALTER TABLE citations ADD COLUMN {col_name} {col_type}"))
                conn.commit()
    except Exception as e:
        _logger.warning(f"Database migration notice: {e}")

def init_db(bind_engine=None):
    if bind_engine is None:
        bind_engine = engine
    Base.metadata.create_all(bind=bind_engine)
    run_migrations(bind_engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

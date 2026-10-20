"""
PulseSync AI - Database Connection Manager & Session Factory
Supports PostgreSQL (Production / Supabase / Neon / Local) with resilient SQLite Development Fallback
"""

import os
import logging
from typing import Generator, Dict, Any
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from .models import Base
from . import workflow_models  # Register additive clinical tables

logger = logging.getLogger("pulsesync.db")
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

RAW_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pulsesync.db")

# Normalise Postgres URL format if necessary (e.g. postgres:// -> postgresql://)
if RAW_DATABASE_URL.startswith("postgres://"):
    RAW_DATABASE_URL = RAW_DATABASE_URL.replace("postgres://", "postgresql://", 1)

def create_active_engine(db_url: str):
    """Attempt creating engine and verifying connection, fallback to SQLite if failed."""
    # Check if URL contains obvious unconfigured placeholders
    if "[YOUR-" in db_url or "[YOUR_" in db_url or "YOUR-PASSWORD" in db_url:
        logger.warning(f"[DB] Placeholder detected in DATABASE_URL ('{db_url}'). Falling back to local SQLite (sqlite:///./pulsesync.db).")
        return create_engine("sqlite:///./pulsesync.db", connect_args={"check_same_thread": False}), "sqlite:///./pulsesync.db"
    
    if db_url.startswith("sqlite"):
        return create_engine(db_url, connect_args={"check_same_thread": False}), db_url

    try:
        test_engine = create_engine(
            db_url,
            pool_size=10,
            max_overflow=20,
            pool_recycle=300,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 2} if "postgresql" in db_url else {}
        )
        # Verify connection
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info(f"[DB] Connected successfully to remote database ({db_url.split('@')[-1] if '@' in db_url else db_url})")
        return test_engine, db_url
    except Exception as exc:
        raise RuntimeError("Configured database connection failed. Check DATABASE_URL; automatic database switching is disabled.") from None

engine, ACTIVE_DATABASE_URL = create_active_engine(RAW_DATABASE_URL)
DATABASE_URL = ACTIVE_DATABASE_URL
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize database tables from SQLAlchemy metadata and ensure all columns exist."""
    # Back up existing SQLite files before an additive schema migration.
    from pathlib import Path
    import shutil
    if engine.dialect.name == "sqlite" and engine.url.database:
        path = Path(engine.url.database)
        if path.exists() and not path.with_suffix(".db.pre-healthflow.bak").exists():
            shutil.copy2(path, path.with_suffix(".db.pre-healthflow.bak"))
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing:
                    # Existing rows remain nullable; ownership is never inferred from order.
                    datatype = column.type.compile(dialect=engine.dialect)
                    connection.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {datatype}'))
        connection.execute(text("UPDATE wards_and_beds SET state = CASE WHEN is_occupied THEN 'OCCUPIED' ELSE 'AVAILABLE' END WHERE state IS NULL"))
        connection.execute(text("UPDATE hospitals SET is_active = true WHERE is_active IS NULL"))

    with engine.begin() as connection:
        connection.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_hospital_owner ON hospitals(user_id) WHERE user_id IS NOT NULL'))


def get_db() -> Generator[Session, None, None]:
    """Dependency for yielding database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_info() -> Dict[str, Any]:
    """Inspect and return current database health, dialect, and table metrics."""
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    
    counts = {}
    with engine.connect() as conn:
        for table in table_names:
            try:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                counts[table] = result.scalar()
            except Exception:
                counts[table] = "N/A"

    return {
        "status": "connected",
        "configured_url": RAW_DATABASE_URL.split("@")[-1] if "@" in RAW_DATABASE_URL else RAW_DATABASE_URL,
        "active_url": ACTIVE_DATABASE_URL.split("@")[-1] if "@" in ACTIVE_DATABASE_URL else ACTIVE_DATABASE_URL,
        "dialect": engine.dialect.name,
        "tables_count": len(table_names),
        "tables": table_names,
        "row_counts": counts
    }

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

logger = logging.getLogger("pulsesync.db")
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

RAW_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:[Bhavika@2803]@db.vgvgappbyxabcigyjfgd.supabase.co:5432/postgres")

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
            connect_args={"connect_timeout": 3} if "postgresql" in db_url else {}
        )
        # Verify connection
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info(f"[DB] Connected successfully to remote database ({db_url.split('@')[-1] if '@' in db_url else db_url})")
        return test_engine, db_url
    except Exception as exc:
        logger.warning(f"[DB] Remote database connection failed ({exc}). Falling back to local SQLite (sqlite:///./pulsesync.db).")
        return create_engine("sqlite:///./pulsesync.db", connect_args={"check_same_thread": False}), "sqlite:///./pulsesync.db"

engine, ACTIVE_DATABASE_URL = create_active_engine(RAW_DATABASE_URL)
DATABASE_URL = ACTIVE_DATABASE_URL
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize database tables from SQLAlchemy metadata and ensure all columns exist."""
    Base.metadata.create_all(bind=engine)
    try:
        with engine.connect() as conn:
            # Safely add any new columns for existing tables
            if engine.dialect.name == "postgresql":
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);"))
                conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS address TEXT;"))
                conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS city VARCHAR(128);"))
                conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;"))
                conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;"))
                conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS aadhaar_card_no VARCHAR(32);"))
                conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS pan_card_no VARCHAR(32);"))
                conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS has_insurance BOOLEAN DEFAULT TRUE;"))
                conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS insurance_claimed BOOLEAN DEFAULT FALSE;"))
                
                conn.execute(text("ALTER TABLE clinics ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;"))
                conn.execute(text("ALTER TABLE clinics ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;"))

                conn.execute(text("ALTER TABLE doctors ADD COLUMN IF NOT EXISTS education VARCHAR(255);"))
                conn.execute(text("ALTER TABLE doctors ADD COLUMN IF NOT EXISTS clinic_name VARCHAR(255);"))
                conn.execute(text("ALTER TABLE doctors ADD COLUMN IF NOT EXISTS clinic_address TEXT;"))
                conn.execute(text("ALTER TABLE doctors ADD COLUMN IF NOT EXISTS patients_checked_count INTEGER DEFAULT 0;"))
                
                conn.execute(text("ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS treatments JSON DEFAULT '[]'::json;"))
                conn.execute(text("ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS total_doctors INTEGER DEFAULT 12;"))
                conn.execute(text("ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS total_wards INTEGER DEFAULT 4;"))
                conn.execute(text("ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;"))
                conn.execute(text("ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;"))
                
                conn.execute(text("ALTER TABLE pharmacy_stores ADD COLUMN IF NOT EXISTS pharmacist_name VARCHAR(255);"))
                conn.execute(text("ALTER TABLE pharmacy_stores ADD COLUMN IF NOT EXISTS city VARCHAR(128);"))
                conn.execute(text("ALTER TABLE pharmacy_stores ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;"))
                conn.execute(text("ALTER TABLE pharmacy_stores ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;"))
                conn.execute(text("ALTER TABLE pharmacy_stores ADD COLUMN IF NOT EXISTS is_online BOOLEAN DEFAULT FALSE;"))
                conn.execute(text("ALTER TABLE pharmacy_stores ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMP;"))
                conn.commit()
            else:
                # SQLite column migration helper
                sqlite_cols = [
                    ("users", "password_hash", "VARCHAR(255)"),
                    ("patients", "latitude", "FLOAT"),
                    ("patients", "longitude", "FLOAT"),
                    ("clinics", "latitude", "FLOAT"),
                    ("clinics", "longitude", "FLOAT"),
                    ("hospitals", "latitude", "FLOAT"),
                    ("hospitals", "longitude", "FLOAT"),
                    ("pharmacy_stores", "latitude", "FLOAT"),
                    ("pharmacy_stores", "longitude", "FLOAT"),
                    ("pharmacy_stores", "is_online", "BOOLEAN DEFAULT 0"),
                    ("pharmacy_stores", "last_active_at", "DATETIME")
                ]
                for tbl, col, col_type in sqlite_cols:
                    try:
                        conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN {col} {col_type};"))
                        conn.commit()
                    except Exception:
                        pass
    except Exception as err:
        logger.warning(f"[DB] Migration check notice: {err}")


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

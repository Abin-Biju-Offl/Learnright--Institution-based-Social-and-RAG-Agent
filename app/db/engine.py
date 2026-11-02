"""
SQLite WAL Database Engine and Session Factory.
"""

from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_FILE = Path(__file__).resolve().parent.parent.parent / "storage" / "ncert_assistant.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

# Engine with check_same_thread=False for FastAPI concurrency
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 15},
    echo=False,
)

# Apply performance and integrity pragmas upon connection
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode = WAL;")        # Non-blocking concurrent reads/writes
    cursor.execute("PRAGMA synchronous = NORMAL;")      # Fast writes with power-loss safety
    cursor.execute("PRAGMA foreign_keys = ON;")         # Strict relational integrity enforcement
    cursor.execute("PRAGMA busy_timeout = 5000;")       # Wait up to 5s during lock contention
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency yielding a transactional SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables defined on Base."""
    DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)

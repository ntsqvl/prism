# =============================================================
# database.py
# Handles PostgreSQL connection to Digital Ocean database.
# Import `get_db` into any router to get a DB session.
# Import `Base` into models to register tables.
# =============================================================

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# -------------------------------------------------------
# Read DATABASE_URL from .env
# Expected format:
# postgresql://username:password@host:port/dbname
#
# Digital Ocean example:
# postgresql://doadmin:YOUR_PASSWORD@db-postgresql-xxx.db.ondigitalocean.com:25060/defaultdb?sslmode=require
# -------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL is not set. "
        "Please add it to your .env file.\n"
        "Format: postgresql://user:password@host:port/dbname?sslmode=require"
    )

# -------------------------------------------------------
# Create SQLAlchemy engine
# pool_pre_ping=True: tests connection before using it
#   (prevents stale connection errors on DO managed DB)
# pool_size: number of persistent connections to keep open
# max_overflow: extra connections allowed beyond pool_size
# -------------------------------------------------------
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,        # Set to True to print all SQL queries (useful for debugging)
)

# -------------------------------------------------------
# Session factory
# autocommit=False: we manually commit transactions
# autoflush=False:  we control when data is flushed to DB
# -------------------------------------------------------
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# -------------------------------------------------------
# Base class for all SQLAlchemy models
# All model files must import this Base and extend it
# -------------------------------------------------------
Base = declarative_base()


# -------------------------------------------------------
# Dependency function for FastAPI routes
# Usage in any router:
#   from app.database import get_db
#   def my_route(db: Session = Depends(get_db)):
#       ...
# -------------------------------------------------------
def get_db():
    """
    Yields a database session for use in a FastAPI route.
    Automatically closes the session when the request is done.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------------------------------------
# Test connection utility
# Run this file directly to verify DB connectivity:
#   python app/database.py
# -------------------------------------------------------
def test_connection():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print("✅ Database connection successful!")
            print(f"   PostgreSQL version: {version}")
    except Exception as e:
        print("❌ Database connection failed!")
        print(f"   Error: {e}")
        print("\n   Check your .env file:")
        print("   DATABASE_URL=postgresql://user:password@host:25060/defaultdb?sslmode=require")


if __name__ == "__main__":
    test_connection()

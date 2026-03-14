from sqlalchemy.orm import Session
from src.db.session import get_db

# Dependency for database session injection
def get_database() -> Session:
    """FastAPI dependency for database sessions"""
    return next(get_db())

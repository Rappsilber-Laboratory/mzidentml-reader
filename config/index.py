"""
index.py
This file contains helper function to get database session
"""

from config.database import SessionLocal


def get_session():
    """
    Helper function to get database session
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

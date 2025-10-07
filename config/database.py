"""
sessions used by sqlalchemy
"""

from .config_parser import get_conn_str
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

conn_str = get_conn_str()

# Create a sqlite engine instance
engine = create_engine(conn_str)

# Create SessionLocal class from sessionmaker factory
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

"""
sessions used by sqlalchemy
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config_parser import get_conn_str

conn_str = get_conn_str()

# Create a sqlite engine instance
engine = create_engine(conn_str)

# Create SessionLocal class from sessionmaker factory
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

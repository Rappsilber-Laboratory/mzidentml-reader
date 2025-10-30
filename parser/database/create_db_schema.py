"""
create_db_schema.py
This script creates a database and schema for the application.
"""

from sqlalchemy import create_engine
from sqlalchemy_utils import create_database, database_exists, drop_database

# noinspection PyUnresolvedReferences
from models import *
from models.base import Base


def create_db(connection_str: str) -> None:
    """Create a database if it doesn't exist.

    Args:
        connection_str: Database connection string
    """
    engine = create_engine(connection_str)
    if not database_exists(engine.url):
        create_database(engine.url)


def drop_db(connection_str: str) -> None:
    """Drop a database if it exists.

    Args:
        connection_str: Database connection string
    """
    import re

    from sqlalchemy import text

    engine = create_engine(connection_str)

    # Extract database name from connection string
    db_match = re.search(r"/([^/?]+)(?:\?|$)", connection_str)
    if not db_match:
        drop_database(engine.url)
        return

    db_name = db_match.group(1)

    # Create connection to postgres database to terminate connections
    postgres_conn_str = connection_str.replace(f"/{db_name}", "/postgres")
    postgres_engine = create_engine(postgres_conn_str)

    try:
        with postgres_engine.connect() as conn:
            # Terminate all connections to the target database
            conn.execute(
                text(
                    f"""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = '{db_name}' AND pid <> pg_backend_pid()
            """
                )
            )
            conn.commit()
    except Exception:
        pass  # Ignore errors if database doesn't exist
    finally:
        postgres_engine.dispose()

    # Now drop the database
    try:
        drop_database(engine.url)
    finally:
        engine.dispose()


def create_schema(connection_str: str) -> None:
    """Create schema for the database.

    Args:
        connection_str: Database connection string
    """
    engine = create_engine(connection_str)  # , echo=True)
    Base.metadata.create_all(engine)
    engine.dispose()


if __name__ == "__main__":
    try:
        from config.config_parser import get_conn_str
    except ModuleNotFoundError:
        raise ModuleNotFoundError(
            "Database credentials missing! "
            "Change default.database.ini and save as database.ini"
        )
    conn_str = get_conn_str()
    create_db(conn_str)
    create_schema(conn_str)

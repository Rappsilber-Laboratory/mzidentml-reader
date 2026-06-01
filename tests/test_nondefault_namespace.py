import logging
import os

from sqlalchemy import create_engine

from parser import MzIdParser
from parser.DatabaseWriter import DatabaseWriter

logger = logging.getLogger(__name__)

FIXTURE = os.path.join(
    os.path.dirname(__file__), "fixtures", "mzid_parser", "nonDefaultnamespace.mzid"
)


def test_nondefault_namespace_mzid_can_be_parsed(tmpdir):
    engine = create_engine(f"sqlite:///{tmpdir}/test.db")
    writer = DatabaseWriter(engine.url, upload_id=1)
    engine.dispose()

    id_parser = MzIdParser.SqliteMzIdParser(FIXTURE, None, writer, logger)
    id_parser.parse()

    if hasattr(writer, "engine"):
        writer.engine.dispose()

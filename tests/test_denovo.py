import logging
import os

import pytest
from sqlalchemy import create_engine

from parser import MzIdParser
from parser.DatabaseWriter import DatabaseWriter
from parser.MzIdParser import MzIdParseException

logger = logging.getLogger(__name__)

DENOVO_FIXTURE = os.path.join(
    os.path.dirname(__file__), "fixtures", "mzid_parser", "denovo_minimal.mzid"
)
MSMS_NO_DBSEQ_FIXTURE = os.path.join(
    os.path.dirname(__file__), "fixtures", "mzid_parser", "msms_no_dbseq.mzid"
)


def test_denovo_search_parses_without_dbseq_or_pepev(tmpdir):
    engine = create_engine(f"sqlite:///{tmpdir}/test.db")
    writer = DatabaseWriter(engine.url, upload_id=1)
    engine.dispose()

    id_parser = MzIdParser.SqliteMzIdParser(DENOVO_FIXTURE, None, writer, logger)
    id_parser.parse()

    assert id_parser.is_de_novo is True

    if hasattr(writer, "engine"):
        writer.engine.dispose()


def test_msms_search_without_dbseq_raises_error(tmpdir):
    engine = create_engine(f"sqlite:///{tmpdir}/test.db")
    writer = DatabaseWriter(engine.url, upload_id=1)
    engine.dispose()

    id_parser = MzIdParser.SqliteMzIdParser(MSMS_NO_DBSEQ_FIXTURE, None, writer, logger)
    with pytest.raises(MzIdParseException, match="No DBSequence elements found"):
        id_parser.parse()

    if hasattr(writer, "engine"):
        writer.engine.dispose()

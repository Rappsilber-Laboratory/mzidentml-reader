import logging
import os

import pytest
from sqlalchemy import create_engine

from parser import MzIdParser
from parser.DatabaseWriter import DatabaseWriter
from parser.MzIdParser import MzIdParseException

logger = logging.getLogger(__name__)

DUP_PE_FIXTURE = os.path.join(
    os.path.dirname(__file__),
    "fixtures",
    "mzid_parser",
    "duplicate_peptide_evidence.mzid",
)


def test_duplicate_peptide_evidence_raises_friendly_error(tmpdir):
    """mzIdentML 1.2 §6.49 violation should surface as MzIdParseException,
    not a raw IntegrityError, with the offending triple in the message."""
    engine = create_engine(f"sqlite:///{tmpdir}/test.db")
    writer = DatabaseWriter(engine.url, upload_id=1)
    engine.dispose()

    id_parser = MzIdParser.SqliteMzIdParser(DUP_PE_FIXTURE, None, writer, logger)
    with pytest.raises(MzIdParseException) as exc_info:
        id_parser.parse()

    msg = str(exc_info.value)
    assert "§6.49" in msg
    assert "peptide_ref=PEP1" in msg
    assert "dBSequence_ref=DBSEQ1" in msg
    assert "start=1" in msg
    assert "duplicate_peptide_evidence.mzid" in msg

    if hasattr(writer, "engine"):
        writer.engine.dispose()

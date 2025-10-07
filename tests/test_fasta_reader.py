import logging
import os
from parser import SimpleFASTA

from .db_pytest_fixtures import *

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def test_full_csv_parser_postgres_mgf(tmpdir, db_info, use_database, engine):
    # file paths
    fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
    fasta_file = os.path.join(fixtures_dir, "test_fasta.fasta")
    db_sequence_dict = SimpleFASTA.get_db_sequence_dict([fasta_file])
    assert len(db_sequence_dict) == 10
    assert db_sequence_dict["A6NFY7"][0] == "A6NFY7"
    assert db_sequence_dict["A6NFY7"][1] == "SDHF1_HUMAN"
    assert db_sequence_dict["A6NFY7"][2] is None
    assert db_sequence_dict["A6NFY7"][3] == (
        "MSRHSRLQRQVLSLYRDLLRAGRGKPGAEARVRAEFRQHAGLPRSDVLR"
        "IEYLYRRGRRQLQLLRSGHATAMGAFVRPRAPTGEPGGVGCQPDDGDSPRNPHDSTGAPETRPDGR"
    )

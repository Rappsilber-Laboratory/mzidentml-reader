import logging
import os

from sqlalchemy import Table

from .db_pytest_fixtures import *
from .parse_mzid import parse_mzid_into_postgresql

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def fixture_path(file):
    current_dir = os.path.dirname(__file__)
    return os.path.join(current_dir, "fixtures", file)


def compare_spectrum_identification(results):
    assert len(results) == 249


def compare_db_sequence(results):
    assert len(results) == 47

    # Check first result
    assert results[0].id == "DBSeq_1_LYSC_CHICK"  # id from mzid
    assert results[0].accession == "LYSC_CHICK"  # accession from mzid
    assert results[0].name == "LYSC_CHICK"
    assert (
        results[0].description
        == "Lysozyme C OS=Gallus gallus OX=9031 GN=LYZ PE=1 SV=1"
    )
    # Verify sequence was loaded (should be 147 aa from UniProt P00698)
    assert len(results[0].sequence) == 147
    assert results[0].sequence.startswith("MRSLLILVLCFLPLAALGKVFGR")

    # Find and check K1C9_HUMAN (should be 623 aa from UniProt P35527)
    k1c9_result = None
    for r in results:
        if r.accession == "K1C9_HUMAN":
            k1c9_result = r
            break

    assert k1c9_result is not None, "K1C9_HUMAN not found in results"
    assert k1c9_result.id == "DBSeq_1_K1C9_HUMAN"
    assert k1c9_result.name == "K1C9_HUMAN"
    assert (
        k1c9_result.description
        == "Keratin, type I cytoskeletal 9 OS=Homo sapiens OX=9606 GN=KRT9 PE=1 SV=3"
    )
    assert len(k1c9_result.sequence) == 623
    assert k1c9_result.sequence.startswith("MSCRQFSSSYLSRSGGGGGGGLGSGGSIR")


def compare_peptide_evidence(results):
    assert len(results) == 1379
    assert (
        results[0].peptide_id == 0
    )  #  'peptide_67_1'  # peptide_ref from <PeptideEvidence>
    assert (
        results[0].dbsequence_id == "DBSeq_1_SCP_CHIOP"
    )  # dbsequence_ref from <PeptideEvidence>
    assert results[0].pep_start == 1  # start from <PeptideEvidence>
    assert not results[0].is_decoy  # is_decoy from <PeptideEvidence>
    assert (
        results[1378].peptide_id == 285
    )  # 'peptide_1497_2_p2'  # peptide_ref from <PeptideEvidence>
    assert (
        results[1378].dbsequence_id == "DBSeq_1_LYSC_CHICK"
    )  # dbsequence_ref from <PeptideEvidence>
    assert results[1378].pep_start == 80  # start from <PeptideEvidence>
    assert not results[1378].is_decoy  # is_decoy from <PeptideEvidence>


def compare_modified_peptide(results):
    assert len(results) == 286

    assert results[0].id == 0  #  'peptide_67_1'  # id from <Peptide> id
    assert results[0].base_sequence == "VATVSLPR"  # value of <PeptideSequence>
    assert results[0].mod_accessions == []
    assert results[0].mod_avg_mass_deltas == []
    assert results[0].mod_monoiso_mass_deltas == []
    assert results[0].mod_positions == []
    assert (
        results[0].link_site1 is None
    )  # location of <Modification> with cross-link acceptor/receiver cvParam
    assert (
        results[0].crosslinker_modmass == 0
    )  # monoisotopicMassDelta of <Modification> with crosslink acc/rec cvParam
    assert (
        results[0].crosslinker_pair_id is None
    )  # value of cross-link acceptor/receiver cvParam

    assert (
        results[1].id == 1
    )  #  'peptide_69_1'  # id from <Peptide> id # mascot seems to duplicate peptides
    assert results[1].base_sequence == "VATVSLPR"  # value of <PeptideSequence>
    assert results[1].mod_accessions == []
    assert results[1].mod_avg_mass_deltas == []
    assert results[1].mod_monoiso_mass_deltas == []
    assert results[1].mod_positions == []
    assert (
        results[1].link_site1 is None
    )  # location of <Modification> with cross-link acceptor/receiver cvParam
    assert (
        results[1].crosslinker_modmass == 0
    )  # monoisotopicMassDelta of <Modification> with crosslink acc/rec cvParam
    assert (
        results[1].crosslinker_pair_id is None
    )  # value of cross-link acceptor/receiver cvParam

    assert (
        results[284].id == 284
    )  #  'peptide_1497_2_p1'  # id from <Peptide> id
    assert (
        results[284].base_sequence == "NLCNIPCSALLSSDITASVNCAK"
    )  # value of <PeptideSequence>
    # Note: first entry is the crosslinker, then the two Nethylmaleimide mods
    assert len(results[284].mod_accessions) == 3
    assert results[284].mod_accessions[1] == {"UNIMOD:108": "Nethylmaleimide"}
    assert results[284].mod_accessions[2] == {"UNIMOD:108": "Nethylmaleimide"}
    assert results[284].mod_avg_mass_deltas == [None, None, None]
    assert results[284].mod_monoiso_mass_deltas[1] == 125.047679
    assert results[284].mod_monoiso_mass_deltas[2] == 125.047679
    assert results[284].mod_positions[1] == 7
    assert results[284].mod_positions[2] == 21
    assert (
        results[284].link_site1 == 3
    )  # location of <Modification> with cross-link acceptor/receiver cvParam
    assert (
        results[284].crosslinker_modmass == -2.01565
    )  # monoisotopicMassDelta of Modification with crosslink cvParam
    assert (
        results[284].crosslinker_pair_id == "37.0"
    )  # value of cross-link acceptor/receiver cvParam

    assert (
        results[285].id == 285
    )  #  'peptide_1497_2_p2'  # id from <Peptide> id
    assert (
        results[285].base_sequence == "WWCNDGR"
    )  # value of <PeptideSequence>
    # Note: mod arrays now include crosslinker entry
    assert len(results[285].mod_accessions) == 1  # Only crosslinker mod
    assert len(results[285].mod_avg_mass_deltas) == 1
    assert len(results[285].mod_monoiso_mass_deltas) == 1
    assert len(results[285].mod_positions) == 1
    assert (
        results[285].link_site1 == 3
    )  # location of <Modification> with cross-link acceptor/receiver cvParam
    assert (
        results[285].crosslinker_modmass == 0
    )  # monoisotopicMassDelta of <Modification> with crosslink acc/rec cvParam
    assert (
        results[285].crosslinker_pair_id == "37.0"
    )  # value of cross-link acceptor/receiver cvParam


def compare_modification(results):
    assert len(results) == 2

    assert results[0].id == 0  # id from incrementing count
    assert results[0].mass == 125.047679  # massDelta from <SearchModification>
    assert results[0].residues == "C"  # residues from <SearchModification>
    assert not results[0].fixed_mod  # fixedMod from <SearchModification>
    # Check accessions dict contains UNIMOD:108
    assert "UNIMOD:108" in results[0].accessions
    assert results[0].accessions["UNIMOD:108"] == "Nethylmaleimide"

    assert results[1].id == 1  # id from incrementing count
    assert results[1].mass == 15.994915  # massDelta from <SearchModification>
    assert results[1].residues == "M"  # residues from <SearchModification>
    assert not results[1].fixed_mod  # fixedMod from <SearchModification>
    # Check accessions dict contains UNIMOD:35
    assert "UNIMOD:35" in results[1].accessions
    assert results[1].accessions["UNIMOD:35"] == "Oxidation"


def compare_enzyme(results):
    assert len(results) == 1

    assert results[0].id == "ENZ_0"  # id from Enzyme element
    assert results[0].protocol_id == "SIP"
    assert results[0].c_term_gain == "OH"
    assert results[0].min_distance is None
    assert results[0].missed_cleavages == 2
    assert results[0].n_term_gain == "H"
    assert results[0].name == "Trypsin/P"
    assert results[0].semi_specific is False
    assert results[0].site_regexp == "(?<=[KR])"
    assert results[0].accession == "MS:1001313"


def test_psql_matrixscience_mzid_parser(use_database, engine):
    # file paths
    fixtures_dir = os.path.join(
        os.path.dirname(__file__), "fixtures", "mzid_parser"
    )
    mzid = os.path.join(fixtures_dir, "F002553.mzid")
    peak_list_folder = False

    id_parser = parse_mzid_into_postgresql(
        mzid, peak_list_folder, logger, use_database, engine
    )

    with engine.connect() as conn:
        # Match
        stmt = Table(
            "match",
            id_parser.writer.meta,
            autoload_with=engine,
            quote=False,
        ).select()
        rs = conn.execute(stmt)
        compare_spectrum_identification(rs.fetchall())

        # DBSequence
        stmt = Table(
            "dbsequence",
            id_parser.writer.meta,
            autoload_with=engine,
            quote=False,
        ).select()
        rs = conn.execute(stmt)
        compare_db_sequence(rs.fetchall())

        # Modification - parsed from <SearchModification>s
        stmt = Table(
            "searchmodification",
            id_parser.writer.meta,
            autoload_with=engine,
            quote=False,
        ).select()
        rs = conn.execute(stmt)
        compare_modification(rs.fetchall())

        # Enzyme - parsed from SpectrumIdentificationProtocols
        stmt = Table(
            "enzyme",
            id_parser.writer.meta,
            autoload_with=engine,
            quote=False,
        ).select()
        rs = conn.execute(stmt)
        compare_enzyme(rs.fetchall())

        # PeptideEvidence
        stmt = Table(
            "peptideevidence",
            id_parser.writer.meta,
            autoload_with=engine,
            quote=False,
        ).select()
        rs = conn.execute(stmt)
        compare_peptide_evidence(rs.fetchall())

        # ModifiedPeptide
        stmt = Table(
            "modifiedpeptide",
            id_parser.writer.meta,
            autoload_with=engine,
            quote=False,
        ).select()
        rs = conn.execute(stmt)
        compare_modified_peptide(rs.fetchall())

        # Spectrum (peak_list_folder = False)
        stmt = Table(
            "spectrum",
            id_parser.writer.meta,
            autoload_with=engine,
            quote=False,
        ).select()
        rs = conn.execute(stmt)
        assert len(rs.fetchall()) == 0

        # ToDo: remaining Tables

    engine.dispose()

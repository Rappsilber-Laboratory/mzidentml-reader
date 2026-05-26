import os
import pytest
from sqlalchemy import Table
import logging
from parser.compression import extract_zip_safe
from parser.csv_parser.XiSpecCsvParser import XiSpecCsvParser
from parser.DatabaseWriter import DatabaseWriter
from .db_pytest_fixtures import *
from .parse_mzid import parse_mzid_into_postgresql
from .test_MzIdParser_ecoli_dsso import (
    compare_db_sequence, compare_modification, compare_enzyme,
    compare_peptide_evidence, compare_modified_peptide,
    compare_spectrum_mgf, compare_spectrum_identification_protocol,
)
from shutil import copyfile
import ntpath
from .parse_csv import parse_full_csv_into_postgresql, parse_links_only_csv_into_postgresql, \
    parse_no_peak_lists_csv_into_postgresql, parse_no_peak_lists_csv_into_sqllite, parse_links_only_csv_into_sqllite, \
    parse_full_csv_into_sqllite

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)


def test_full_csv_parser_postgres_mgf(tmpdir, db_info, use_database, engine):
    # file paths
    fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures', 'csv_parser', 'full_csv_mgf')
    csv = os.path.join(fixtures_dir, 'PolII_XiVersion1.6.742_PSM_xiFDR1.1.27.csv')
    peaklist_zip_file = os.path.join(fixtures_dir, 'Rappsilber_CLMS_PolII_MGFs.zip')
    unzip_dir = os.path.join(str(tmpdir), ntpath.basename(peaklist_zip_file) + '_unzip')
    peak_list_folder = extract_zip_safe(peaklist_zip_file, unzip_dir)
    fasta_file = os.path.join(fixtures_dir, 'polII-uniprot.fasta')
    # copy fasta file to tmpdir so it is being read by the parser
    copyfile(fasta_file, os.path.join(str(tmpdir), ntpath.basename(fasta_file)))

    id_parser = parse_full_csv_into_postgresql(csv, peak_list_folder, tmpdir, logger, use_database, engine)

    with engine.connect() as conn:

        # DBSequence
        stmt = Table("dbsequence", id_parser.writer.meta, autoload_with=id_parser.writer.engine,
                     quote=False).select()
        conn.execute(stmt)
        # compare_db_sequence(rs.fetchall())


def test_no_peak_lists_csv_parser_postgres(tmpdir, db_info, use_database, engine):
    # file paths
    fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures', 'csv_parser',
                                'nopeaklist_csv')
    csv = os.path.join(fixtures_dir, 'PolII_nopeaklist.csv')
    fasta_file = os.path.join(fixtures_dir, 'polII-uniprot.fasta')
    # copy fasta file to tmpdir so it is being read by the parser
    copyfile(fasta_file, os.path.join(str(tmpdir), ntpath.basename(fasta_file)))

    # parse the csv file
    parse_no_peak_lists_csv_into_postgresql(csv, None, tmpdir, logger, use_database, engine)


def test_links_only_csv_parser_postgres(tmpdir, db_info, use_database, engine):
    # file paths
    fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures', 'csv_parser', 'linksonly_csv')
    csv = os.path.join(fixtures_dir, 'results.csv')
    fasta_file = os.path.join(fixtures_dir, 'results.fasta')
    # copy fasta file to tmpdir so it is being read by the parser
    copyfile(fasta_file, os.path.join(str(tmpdir), ntpath.basename(fasta_file)))

    # parse the csv file
    parse_links_only_csv_into_postgresql(csv, None, tmpdir, logger, use_database, engine)


def test_ambiguous_links_only_csv_parser_postgres(tmpdir, db_info, use_database, engine):
    # file paths
    fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures', 'csv_parser', 'linksonly_csv')
    csv = os.path.join(fixtures_dir, 'test_GH.csv')
    # parse the csv file
    id_parser = parse_links_only_csv_into_postgresql(csv, None, tmpdir, logger, use_database, engine)

    with engine.connect() as conn:
        # PeptideEvidence
        stmt = Table("peptideevidence", id_parser.writer.meta,
                     autoload_with=id_parser.writer.engine, quote=False).select()
        rs = conn.execute(stmt)
        results = rs.fetchall()
        assert len(results) == 6


def test_full_csv_parser_sqllite_mgf(tmpdir, db_info, use_database, engine):
    # file paths
    fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures', 'csv_parser', 'full_csv_mgf')
    csv = os.path.join(fixtures_dir, 'PolII_XiVersion1.6.742_PSM_xiFDR1.1.27.csv')
    peaklist_zip_file = os.path.join(fixtures_dir, 'Rappsilber_CLMS_PolII_MGFs.zip')
    unzip_dir = os.path.join(str(tmpdir), ntpath.basename(peaklist_zip_file) + '_unzip')
    peak_list_folder = extract_zip_safe(peaklist_zip_file, unzip_dir)
    fasta_file = os.path.join(fixtures_dir, 'polII-uniprot.fasta')
    # copy fasta file to tmpdir so it is being read by the parser
    copyfile(fasta_file, os.path.join(str(tmpdir), ntpath.basename(fasta_file)))
    test_database = os.path.join(str(tmpdir), 'test.db')

    conn_str = f'sqlite:///{test_database}'
    engine = create_engine(conn_str)

    id_parser = parse_full_csv_into_sqllite(csv, peak_list_folder, tmpdir, logger, use_database, engine)

    with engine.connect() as conn:

        # DBSequence
        stmt = Table("DBSequence", id_parser.writer.meta, autoload_with=id_parser.writer.engine,
                     quote=False).select()
        conn.execute(stmt)
        # compare_db_sequence(rs.fetchall())


def test_no_peak_lists_csv_parser_sqllite(tmpdir, db_info, use_database, engine):
    # file paths
    fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures', 'csv_parser',
                                'nopeaklist_csv')
    csv = os.path.join(fixtures_dir, 'PolII_nopeaklist.csv')
    fasta_file = os.path.join(fixtures_dir, 'polII-uniprot.fasta')
    # copy fasta file to tmpdir so it is being read by the parser
    copyfile(fasta_file, os.path.join(str(tmpdir), ntpath.basename(fasta_file)))
    test_database = os.path.join(str(tmpdir), 'test.db')

    conn_str = f'sqlite:///{test_database}'
    engine = create_engine(conn_str)

    # parse the csv file
    parse_no_peak_lists_csv_into_sqllite(csv, None, tmpdir, logger, use_database, engine)


def test_links_only_csv_parser_sqllite(tmpdir, db_info, use_database, engine):
    # file paths
    fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures', 'csv_parser', 'linksonly_csv')
    csv = os.path.join(fixtures_dir, 'results.csv')
    fasta_file = os.path.join(fixtures_dir, 'results.fasta')
    # copy fasta file to tmpdir so it is being read by the parser
    copyfile(fasta_file, os.path.join(str(tmpdir), ntpath.basename(fasta_file)))
    test_database = os.path.join(str(tmpdir), 'test.db')

    conn_str = f'sqlite:///{test_database}'
    engine = create_engine(conn_str)

    # parse the csv file
    parse_links_only_csv_into_sqllite(csv, None, tmpdir, logger, use_database, engine)


def test_xispec_csv_parser_mzml(tmpdir):
    # file paths
    fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures', 'csv_parser', 'xispec_mzml')
    csv = os.path.join(fixtures_dir, 'example.csv')
    peaklist_zip_file = os.path.join(fixtures_dir, 'example.mzML.zip')
    unzip_dir = os.path.join(str(tmpdir), ntpath.basename(peaklist_zip_file) + '_unzip')
    peak_list_folder = extract_zip_safe(peaklist_zip_file, unzip_dir)
    test_database = os.path.join(str(tmpdir), 'test.db')

    conn_str = f'sqlite:///{test_database}'
    engine = create_engine(conn_str)

    writer = DatabaseWriter(engine.url)
    engine.dispose()

    id_parser = XiSpecCsvParser(csv, str(tmpdir), peak_list_folder, writer, logger)
    id_parser.check_required_columns()
    id_parser.parse()

    if hasattr(writer, 'engine'):
        writer.engine.dispose()

def test_psql_mgf_mzid_parser(use_database, engine):
    # file paths
    fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures', 'mzid_parser')
    mzid = os.path.join(fixtures_dir, 'mgf_ecoli_dsso.mzid')
    peak_list_folder = os.path.join(fixtures_dir, 'peaklist')

    id_parser = parse_mzid_into_postgresql(mzid, peak_list_folder, logger, use_database, engine)

    with engine.connect() as conn:

        # DBSequence
        stmt = Table("dbsequence", id_parser.writer.meta, autoload_with=engine, quote=False).select()
        rs = conn.execute(stmt)
        compare_db_sequence(rs.fetchall())

        # SearchModification - parsed from <SearchModification>s
        stmt = Table("searchmodification", id_parser.writer.meta, autoload_with=engine, quote=False).select()
        rs = conn.execute(stmt)
        compare_modification(rs.fetchall())

        # Enzyme - parsed from SpectrumIdentificationProtocols
        stmt = Table("enzyme", id_parser.writer.meta, autoload_with=engine, quote=False).select()
        rs = conn.execute(stmt)
        compare_enzyme(rs.fetchall())

        # PeptideEvidence
        stmt = Table("peptideevidence", id_parser.writer.meta, autoload_with=engine, quote=False).select()
        rs = conn.execute(stmt)
        compare_peptide_evidence(rs.fetchall())

        # ModifiedPeptide
        stmt = Table("modifiedpeptide", id_parser.writer.meta, autoload_with=engine, quote=False).select()
        rs = conn.execute(stmt)
        compare_modified_peptide(rs.fetchall())

        # Spectrum
        compare_spectrum_mgf(conn, peak_list_folder)

        # Match
        stmt = Table("match", id_parser.writer.meta, autoload_with=engine, quote=False).select()
        rs = conn.execute(stmt)
        assert 22 == rs.rowcount
        results = rs.fetchall()
        assert results[0].id == 'SII_3_1'
        assert results[0].spectrum_id == 'index=3'
        assert results[0].spectra_data_id == 1
        assert results[0].pep1_id == 4
        assert results[0].pep2_id == 5
        assert results[0].charge_state == 5
        assert results[0].pass_threshold
        assert results[0].rank == 1
        assert results[0].scores == {'xi:score': 33.814201}
        assert results[0].exp_mz == 945.677359
        assert results[0].calc_mz == pytest.approx(945.6784858667701, abs=1e-12)

        # SpectrumIdentificationProtocol
        stmt = Table("spectrumidentificationprotocol", id_parser.writer.meta,
                     autoload_with=engine, quote=False).select()
        rs = conn.execute(stmt)
        compare_spectrum_identification_protocol(rs.fetchall())

        # Upload
        stmt = Table("upload", id_parser.writer.meta, autoload_with=engine, quote=False).select()
        rs = conn.execute(stmt)
        assert 1 == rs.rowcount
        results = rs.fetchall()
        assert results[0].identification_file_name == 'mgf_ecoli_dsso.mzid'
        assert results[0].provider == {
            'id': 'PROVIDER',
            'ContactRole': [{'contact_ref': 'PERSON_DOC_OWNER', 'Role': 'researcher'}],
        }
        assert results[0].audit_collection == {
            'Organization': {'contact name': 'TU Berlin', 'id': 'ORG_DOC_OWNER', 'name': 'TU Berlin'},
            'Person': {
                'Affiliation': [{'organization_ref': 'ORG_DOC_OWNER'}],
                'contact address': 'TIB 4/4-3 Gebäude 17, Aufgang 1, Raum 476 Gustav-Meyer-Allee 25 13355 Berlin',
                'contact email': 'lars.kolbowski@tu-berlin.de',
                'firstName': 'Lars',
                'id': 'PERSON_DOC_OWNER',
                'lastName': 'Kolbowski',
            },
        }
        assert results[0].analysis_sample_collection == {}
        assert results[0].bib == []
        assert results[0].contains_crosslinks
        assert results[0].upload_warnings == []

    engine.dispose()


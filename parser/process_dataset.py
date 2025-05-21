"""Script to process mzIdentML files, typically to load their data into a relational database."""
import argparse
import ftplib
import gc
import logging.config
import os
import traceback
import tempfile

import shutil
import socket
import sys
import time
from urllib.parse import urlparse

import orjson
import requests
from sqlalchemy import create_engine, text

# Import custom modules
from config.config_parser import get_conn_str
from parser.APIWriter import APIWriter
from parser.DatabaseWriter import DatabaseWriter
from parser.MzIdParser import MzIdParser, SqliteMzIdParser
from parser.schema_validate import schema_validate

# Configure logging
import logging.config
import importlib.resources

try:
    # Access `logging.ini` as a resource inside the package
    with importlib.resources.path('config', 'logging.ini') as logging_config_path:
        logging.config.fileConfig(logging_config_path)
        logger = logging.getLogger(__name__)
except FileNotFoundError:
    # Fall back to basic config if `logging.ini` is missing
    logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.info("Logging configuration file not found, falling back to basic config.")

def parse_arguments():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Process mzIdentML files in a dataset and load them into a relational database.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-p', '--pxid', nargs='+',
                       help='proteomeXchange accession, should be of the form PXDnnnnnn or numbers only', )
    group.add_argument('-f', '--ftp',
                       help='Process files from specified ftp location, e.g. ftp://ftp.jpostdb.org/JPST001914/')
    group.add_argument('-d', '--dir',
                       help='Process files in specified local directory, e.g. /home/user/data/JPST001914')
    group.add_argument('-v', '--validate',
                       help='Validate mzIdentML file or files in specified folder against 1.2.0 or 1.3.0 XSD schema, '
                            'and check for other errors, including in referencing of peaklists. '
                            'AND check that Seq elements are present for target proteins '
                            '(this not being a requirement of the schema for validity). '
                            'If argument is directory all MzIdentmL files in it will be checked, '
                            'but it exits after first failure.'
                            'If its a specific file then this file will be checked.'
                            'The referenced peaklist files must be present alongside the MzIdentML files,'
                            'i.e. contained in the same directory as them.')
    group.add_argument('--seqsandresiduepairs',
                       help='Output JSON with sequences and residue pairs,'
                            'if argument is directory all MzIdentmL files in it will be read. '
                            'If --temp option is given then the temp folder will be used for the sqlite DB file, '
                            'otherwise an in-memory sqlite DB will be used. '
                       )

    parser.add_argument('-i', '--identifier',
                        help='Identifier to use for dataset (if providing '
                             'proteomeXchange accession these are always used instead and this arg is ignored),'
                             'if provbiding directory then default is the directory name')
    parser.add_argument('--dontdelete', action='store_true',
                        help="Don't delete downloaded data after processing")
    parser.add_argument('-t', '--temp', action='store_true',
                        help='Temp folder to download data files into or to create temp sqlite DB in.'
                             '(default: system temp directory)')
    parser.add_argument('-n', '--nopeaklist',
                        help='No peak list files available, only works in combination with --dir arg',
                        action='store_true')
    parser.add_argument('-w', '--writer', help='Save data to database(-w db) or API(-w api)')

    return parser.parse_args()


def process_pxid(px_accessions, temp_dir, writer_method, dontdelete):
    """Processes ProteomeXchange accessions."""
    for px_accession in px_accessions:
        convert_pxd_accession_from_pride(px_accession, temp_dir, writer_method, dontdelete)


def process_ftp(ftp_url, temp_dir, project_identifier, writer_method, dontdelete):
    """Processes data from an FTP URL."""
    if not project_identifier:
        project_identifier = urlparse(ftp_url).path.rsplit("/", 1)[-1]
    convert_from_ftp(ftp_url, temp_dir, project_identifier, writer_method, dontdelete)


def process_dir(local_dir, project_identifier, writer_method, nopeaklist):
    """Processes data from a local directory."""
    if not project_identifier:
        project_identifier = local_dir.rsplit("/", 1)[-1]
    convert_dir(local_dir, project_identifier, writer_method, nopeaklist=nopeaklist)


def validate(validate_arg, tmpdir):
    """Validates mzIdentML files against the XSD schema, then checks for other errors.
    This includes checking that Seq elements are present for target proteins,
    even though omitting them is technically valid.
    Prints out results.
    :param validate_arg: str
        The path to the mzIdentML file or directory to be validated.
    :param tmpdir: str
        The temporary directory to use for validation - an Sqlite DB is created here.
    :return: None
    """
    if os.path.isdir(validate_arg):
        print(f'Validating directory: {validate_arg}')
        for file in os.listdir(validate_arg):
            if file.endswith(".mzid"):
                file_to_validate = os.path.join(validate_arg, file)
                if validate_file(file_to_validate, tmpdir):
                    print(f'Validation successful for file {file_to_validate}.')
                else:
                    print(f'Validation failed for file {file_to_validate}. Exiting.')
                    sys.exit(1)
        print(f'SUCCESS! Directory {validate_arg} validation complete. Exciting.')
    else:
        if not validate_file(validate_arg, tmpdir):
            print(f'Validation failed for file {validate_arg}. Exiting.')
            sys.exit(1)
        print(f'SUCCESS! File {validate_arg} validation complete. Exciting.')

    sys.exit(0)


def json_sequences_and_residue_pairs(filepath, tmpdir):
    """Returns json of sequences and residue pairs from mzIdentML files.
    Parameters
    ----------
    filepath : str
        The path to the mzIdentML file to be validated.
    tmpdir : str
        The temporary directory to use for validation - an Sqlite DB is created here if given,
        otherwise an in-memory sqlite DB is used.
    """
    return orjson.dumps(sequences_and_residue_pairs(filepath, tmpdir))


def sequences_and_residue_pairs(filepath, tmpdir):
    """Prints json of sequences and residue pairs from mzIdentML files
    Parameters
    ----------
    filepath : str
        The path to the mzIdentML file to be validated.
    tmpdir : str
        The temporary directory to use for validation - an Sqlite DB is created here if given,
        otherwise an in-memory sqlite DB is used.
    """
    file = os.path.basename(filepath)
    filewithoutext = os.path.splitext(file)[0]
    temp_database = os.path.join(str(tmpdir), f'{filewithoutext}.db')

    # tempdir is currently always set
    # if tmpdir:
    # delete the temp database if it exists
    if os.path.exists(temp_database):
        os.remove(temp_database)

    conn_str = f'sqlite:///{temp_database}'
    # else: # not working
    #     conn_str = 'sqlite:///:memory:?cache=shared'

    engine = create_engine(conn_str)

    if os.path.isdir(filepath):
        for file in os.listdir(filepath):
            mzid_count = 0
            if file.endswith(".mzid"):
                mzid_count += 1
                file_to_process = os.path.join(filepath, file)
                read_sequences_and_residue_pairs(file_to_process, mzid_count, conn_str)
    elif os.path.isfile(filepath):
        if filepath.endswith(".mzid"):
            read_sequences_and_residue_pairs(filepath, 0, conn_str)
        else:
            raise ValueError(f'Invalid file path (must end ".mzid"): {filepath}')
    else:
        raise ValueError(f'Invalid file or directory path: {filepath}')

    with engine.connect() as conn:
        try:
            # get sequences
            sql = text("""
            SELECT dbseq.id, u.identification_file_name as file, dbseq.sequence, dbseq.accession
            FROM upload AS u
            JOIN dbsequence AS dbseq ON u.id = dbseq.upload_id
            INNER JOIN peptideevidence pe ON dbseq.id = pe.dbsequence_id AND dbseq.upload_id = pe.upload_id
            WHERE pe.is_decoy = false
            GROUP BY dbseq.id, dbseq.sequence, dbseq.accession, u.identification_file_name;
            """)
            rs = conn.execute(sql)
            seq_rows = rs.mappings().all()
            seq_rows = [dict(row) for row in seq_rows]
            # seq_rows = rs.fetchall()
            logging.info("Successfully fetched sequences")

            # get residue pairs
            sql = text("""SELECT group_concat(si.id) as match_ids, group_concat(u.identification_file_name) as files,
            pe1.dbsequence_id as prot1, dbs1.accession as prot1_acc, (pe1.pep_start + mp1.link_site1 - 1) as pos1,
            pe2.dbsequence_id as prot2, dbs2.accession as prot2_acc, (pe2.pep_start + mp2.link_site1 - 1) as pos2,
			coalesce (mp1.crosslinker_accession, mp2.crosslinker_accession) as crosslinker_accession
            FROM match si INNER JOIN
            modifiedpeptide mp1 ON si.upload_id = mp1.upload_id AND si.pep1_id = mp1.id INNER JOIN
            peptideevidence pe1 ON mp1.upload_id = pe1.upload_id AND  mp1.id = pe1.peptide_id INNER JOIN
            dbsequence dbs1 ON pe1.upload_id = dbs1.upload_id AND pe1.dbsequence_id = dbs1.id INNER JOIN
            modifiedpeptide mp2 ON si.upload_id = mp2.upload_id AND si.pep2_id = mp2.id INNER JOIN
            peptideevidence pe2 ON mp2.upload_id = pe2.upload_id AND mp2.id = pe2.peptide_id INNER JOIN
            dbsequence dbs2 ON pe2.upload_id = dbs2.upload_id AND pe2.dbsequence_id = dbs2.id INNER JOIN
            upload u on u.id = si.upload_id
            WHERE mp1.link_site1 > 0 AND mp2.link_site1 > 0 AND pe1.is_decoy = false AND pe2.is_decoy = false
            AND si.pass_threshold = true
            GROUP BY pe1.dbsequence_id , dbs1.accession, pos1, pe2.dbsequence_id, dbs2.accession , pos2
            ORDER BY pe1.dbsequence_id , pos1, pe2.dbsequence_id, pos2
            ;""")
            start_time = time.time()
            rs = conn.execute(sql)
            elapsed_time = time.time() - start_time
            logging.info(f"residue pair SQL execution time: {elapsed_time}")
            rp_rows = rs.mappings().all()
            rp_rows = [dict(row) for row in rp_rows]
            # rp_rows = rs.fetchall()
        except Exception as error:
            raise error
        finally:
            conn.close()
    os.remove(temp_database)
    return {"sequences": seq_rows, "residue_pairs": rp_rows}


def main():
    """Main function to execute script logic."""
    args = parse_arguments()
    temp_dir = os.path.expanduser(args.temp) if args.temp else tempfile.gettempdir()
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    if args.writer and args.writer.lower() not in {'api', 'db'}:
        raise ValueError('Writer method not supported! Please use "api" or "db".')
    writer_type = args.writer if args.writer else 'db'

    try:
        if args.pxid:
            process_pxid(args.pxid, temp_dir, writer_type, args.dontdelete)
        elif args.ftp:
            process_ftp(args.ftp, temp_dir, args.identifier, writer_type, args.dontdelete)
        elif args.dir:
            process_dir(args.dir, args.identifier, writer_type, args.nopeaklist)
        elif args.validate:
            validate(args.validate, temp_dir)
        elif args.seqsandresiduepairs:
            print(json_sequences_and_residue_pairs(args.seqsandresiduepairs, temp_dir))
        sys.exit(0)
    except Exception as ex:
        logger.error(ex)
        traceback.print_exc()
        sys.exit(1)


def convert_pxd_accession(px_accession, temp_dir, writer_method, dontdelete):
    """get ftp location from PX"""
    px_url = f'https://proteomecentral.proteomexchange.org/cgi/GetDataset?ID={px_accession}&outputMode=JSON'
    logger.info(f'GET request to ProteomeExchange: {px_url}')
    px_response = requests.get(px_url)

    if px_response.status_code == 200:
        logger.info('ProteomeExchange returned status code 200')
        px_json = px_response.json()
        ftp_url = None
        for dataSetLink in px_json['fullDatasetLinks']:
            # name check is necessary because some things have wrong acc, e.g. PXD006574
            if dataSetLink['accession'] == "MS:1002852" or dataSetLink['name'] == "Dataset FTP location":
                ftp_url = dataSetLink['value']
                convert_from_ftp(ftp_url, temp_dir, px_accession, writer_method, dontdelete)
                break
        if not ftp_url:
            raise Exception('Error: Dataset FTP location not found in ProteomeXchange response')
    else:
        raise Exception(f'Error: ProteomeXchange returned status code {px_response.status_code}')


def convert_pxd_accession_from_pride(px_accession, temp_dir, writer_method, dontdelete):
    """get ftp location from PRIDE API"""
    px_url = f'https://www.ebi.ac.uk/pride/ws/archive/v2/files/byProject?accession={px_accession}'
    logger.info(f'GET request to PRIDE API: {px_url}')
    pride_response = requests.get(px_url)

    if pride_response.status_code == 200:
        logger.info('PRIDE API returned status code 200')
        pride_json = pride_response.json()
        ftp_url = None

        if pride_json:
            for protocol in pride_json[0].get('publicFileLocations', []):
                if protocol['name'] == "FTP Protocol":
                    parsed_url = urlparse(protocol['value'])
                    parent_folder = f"{parsed_url.scheme}://{parsed_url.netloc}" + "/".join(
                        parsed_url.path.split('/')[:-1])
                    logger.info(f'PRIDE FTP path : {parent_folder}')
                    ftp_url = parent_folder
                    break
        if ftp_url:
            convert_from_ftp(ftp_url, temp_dir, px_accession, writer_method, dontdelete)
        else:
            raise Exception('Error: Public File location not found in PRIDE API response')
    else:
        raise Exception(f'Error: PRIDE API returned status code {pride_response.status_code}')


def convert_from_ftp(ftp_url, temp_dir, project_identifier, writer_method, dontdelete):
    """Downloads and converts data from an FTP URL."""
    if not ftp_url.startswith('ftp://'):
        raise Exception('Error: FTP location must start with ftp://')

    # Create temp directory if not exists
    os.makedirs(temp_dir, exist_ok=True)
    logger.info(f'FTP url: {ftp_url}')

    path = os.path.join(temp_dir, project_identifier)
    os.makedirs(path, exist_ok=True)

    ftp_ip = socket.getaddrinfo(urlparse(ftp_url).hostname, 21)[0][4][0]
    files = get_ftp_file_list(ftp_ip, urlparse(ftp_url).path)
    for f in files:
        if not (os.path.isfile(os.path.join(str(path), f))
                or f.lower == "generated"  # dunno what these files are but they seem to make ftp break
                or f.lower().endswith('raw')
                or f.lower().endswith('raw.gz')
                or f.lower().endswith('all.zip')
                or f.lower().endswith('csv')
                or f.lower().endswith('txt')):
            logger.info(f'Downloading {f} to {path}')
            ftp = get_ftp_login(ftp_ip)
            try:
                ftp.cwd(urlparse(ftp_url).path)
                with open(os.path.join(str(path), f), 'wb') as file:
                    ftp.retrbinary(f"RETR {f}", file.write)
                ftp.quit()
            except ftplib.error_perm as e:
                ftp.quit()
                raise e

    convert_dir(path, project_identifier, writer_method)

    if not dontdelete:
        try:
            shutil.rmtree(path)
        except OSError as e:
            logger.error(f'Failed to delete temp directory {path}')
            raise e


def get_ftp_login(ftp_ip):
    """Logs in to an FTP server."""
    time.sleep(10)  # Delay to avoid rate limiting
    try:
        ftp = ftplib.FTP(ftp_ip)
        ftp.login()  # Uses password: anonymous@
        return ftp
    except ftplib.all_errors as e:
        logger.error(f'FTP login failed at {time.strftime("%c")}')
        raise e


def get_ftp_file_list(ftp_ip, ftp_dir):
    """Gets a list of files from an FTP directory."""
    ftp = get_ftp_login(ftp_ip)
    try:
        ftp.cwd(ftp_dir)
    except ftplib.error_perm as e:
        logger.error(f"{ftp_dir}: {e}")
        ftp.quit()
        raise e
    try:
        return ftp.nlst()
    except ftplib.error_perm as e:
        if str(e) == "550 No files found":
            logger.info(f"FTP: No files in {ftp_dir}")
        else:
            logger.error(f"{ftp_dir}: {e}")
        raise e
    finally:
        ftp.close()


def convert_dir(local_dir, project_identifier, writer_method, nopeaklist=False):
    """Converts files in a local directory."""
    peaklist_dir = None if nopeaklist else local_dir
    for file in os.listdir(local_dir):
        if file.endswith((".mzid", ".mzid.gz")):
            logger.info(f"Processing {file}")
            conn_str = get_conn_str()
            if writer_method.lower() == 'api':
                writer = APIWriter(pxid=project_identifier)
            else:
                writer = DatabaseWriter(conn_str, pxid=project_identifier)
            id_parser = MzIdParser(os.path.join(local_dir, file), local_dir, peaklist_dir, writer, logger)
            try:
                id_parser.parse()
                # logger.info(id_parser.warnings + "\n")
            except Exception as e:
                logger.error(f"Error parsing {file}")
                logger.exception(e)
                raise e
            gc.collect()


def validate_file(filepath, tmpdir):
    """
    Validates mzIdentML files against the 1.2.0 or 1.3.0 schema, then checks for some other errors.

    Parameters
    ----------
    filepath : str
        The path to the mzIdentML file to be validated.
    tmpdir : str
        The temporary directory to use for validation - an Sqlite DB is created here.

    Returns
    -------
    bool
        True if the file is valid, False otherwise.
    """
    print(f'Validating file {filepath}.')

    local_dir = os.path.dirname(filepath)
    file = os.path.basename(filepath)

    if not file.endswith(".mzid"):
        raise ValueError(f'Invalid file path (must end ".mzid"): {filepath}')

    if schema_validate(filepath):
        print(f'File {filepath} is schema valid.')

        filewithoutext = os.path.splitext(file)[0]
        test_database = os.path.join(str(tmpdir), f'{filewithoutext}.db')
        # delete the test database if it exists
        if os.path.exists(test_database):
            os.remove(test_database)
        conn_str = f'sqlite:///{test_database}'
        engine = create_engine(conn_str)

        # switch on Foreign Key Enforcement
        with engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON;"))

        writer = DatabaseWriter(conn_str, upload_id=1, pxid="Validation")
        id_parser = SqliteMzIdParser(os.path.join(local_dir, file), local_dir, local_dir, writer, logger)
        try:
            id_parser.parse()
            os.remove(test_database)
        except Exception as e:
            print(f"Error parsing {filepath}")
            print(e)
            return False

    else:
        print(f'File {filepath} is schema invalid.')
        return False

    return True


def read_sequences_and_residue_pairs(filepath, upload_id, conn_str):
    """
    get sequences and residue pairs from mzIdentML files

    Parameters
    ----------
    filepath : str
        The path to the mzIdentML file to be validated.
    upload_id : int
        The upload id to use for the sequences and residue pairs.
    conn_str : str
        The connection string to use for the sqlite database.

    Returns
    -------
    None
    """

    local_dir = os.path.dirname(filepath)
    writer = DatabaseWriter(conn_str, upload_id, pxid="Validation")
    id_parser = SqliteMzIdParser(filepath, local_dir, local_dir, writer, logger)
    try:
        id_parser.parse()
    except Exception as e:
        print(f"Error parsing {filepath}")
        raise e


if __name__ == "__main__":
    main()

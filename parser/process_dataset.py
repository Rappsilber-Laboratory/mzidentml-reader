"""Script to process mzIdentML files, typically to load their data into a relational database."""

import argparse
import ftplib
import gc
import importlib.resources

# Configure logging
import logging.config
import os
import shutil
import socket
import sys
import tempfile
import time
import traceback
from parser.APIWriter import APIWriter
from parser.DatabaseWriter import DatabaseWriter
from parser.MzIdParser import MzIdParser, SqliteMzIdParser
from parser.schema_validate import schema_validate
from urllib.parse import urlparse

import orjson
import requests
from sqlalchemy import create_engine, text

# Import custom modules
from config.config_parser import get_conn_str

# FTP download exclusions
SKIP_EXTENSIONS = (".raw", ".raw.gz", ".all.zip", ".csv", ".txt")
SKIP_DIRS = ("generated",)

try:
    # Access `logging.ini` as a resource inside the package
    with importlib.resources.path(
        "config", "logging.ini"
    ) as logging_config_path:
        logging.config.fileConfig(logging_config_path)
        logger = logging.getLogger(__name__)
except FileNotFoundError:
    # Fall back to basic config if `logging.ini` is missing
    logging.basicConfig(
        level=logging.ERROR,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configuration file not found, falling back to basic config."
    )


def _create_temp_database(temp_dir: str, filename: str) -> str:
    """Create a temporary SQLite database.

    Args:
        temp_dir: Directory to create the temporary database in.
        filename: Base filename (without extension) for the database file.

    Returns:
        SQLAlchemy connection string for the temporary database.
    """
    filewithoutext = os.path.splitext(filename)[0]
    temp_database = os.path.join(str(temp_dir), f"{filewithoutext}.db")

    # Delete the temp database if it exists
    if os.path.exists(temp_database):
        os.remove(temp_database)

    return f"sqlite:///{temp_database}"


def _dispose_writer_engine(writer) -> None:
    """Dispose of the writer's database engine to close connections.

    Args:
        writer: Writer instance that may have an engine attribute.
    """
    if hasattr(writer, "engine"):
        writer.engine.dispose()


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Process mzIdentML files in a dataset and load them into a relational database."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-p",
        "--pxid",
        nargs="+",
        help="proteomeXchange accession, should be of the form PXDnnnnnn or numbers only",
    )
    group.add_argument(
        "-f",
        "--ftp",
        help="Process files from specified ftp location, e.g. ftp://ftp.jpostdb.org/JPST001914/",
    )
    group.add_argument(
        "-d",
        "--dir",
        help="Process files in specified local directory, e.g. /home/user/data/JPST001914",
    )
    group.add_argument(
        "-v",
        "--validate",
        help="Validate mzIdentML file or files in specified folder against 1.2.0 or 1.3.0 XSD schema, "
        "and check for other errors, including in referencing of peaklists. "
        "AND check that Seq elements are present for target proteins "
        "(this not being a requirement of the schema for validity). "
        "If argument is directory all MzIdentmL files in it will be checked, "
        "but it exits after first failure."
        "If its a specific file then this file will be checked."
        "The referenced peaklist files must be present alongside the MzIdentML files,"
        "i.e. contained in the same directory as them.",
    )
    group.add_argument(
        "--seqsandresiduepairs",
        help="Output JSON with sequences and residue pairs,"
        "if argument is directory all MzIdentmL files in it will be read. "
        "If --temp option is given then the temp folder will be used for the sqlite DB file.",
        type=str,
    )

    parser.add_argument(
        "-j",
        "--json",
        help="JSON filename",
        type=str,
        required=False,
    )

    parser.add_argument(
        "-i",
        "--identifier",
        help="Identifier to use for dataset (if providing "
        "proteomeXchange accession these are always used instead and this arg is ignored),"
        "if providing directory then default is the directory name",
    )
    parser.add_argument(
        "--dontdelete",
        action="store_true",
        help="Don't delete downloaded data after processing",
    )
    parser.add_argument(
        "-t",
        "--temp",
        help="Temp folder to download data files into or to create temp sqlite DB in."
        "(default: system temp directory)",
        type=str,
    )
    parser.add_argument(
        "-n",
        "--nopeaklist",
        help="No peak list files available, works with --dir and --validate "
        "(not supported with --pxid or --ftp)",
        action="store_true",
    )
    parser.add_argument(
        "-w", "--writer", help="Save data to database(-w db) or API(-w api)"
    )

    args = parser.parse_args()

    # Validate that -j/--json is provided when using --seqsandresiduepairs
    if args.seqsandresiduepairs and not args.json:
        parser.error(
            "The -j/--json argument is required when using "
            "--seqsandresiduepairs"
        )

    # Validate writer argument only if it's going to be used
    if (args.pxid or args.ftp or args.dir) and args.writer:
        if args.writer.lower() not in {"api", "db"}:
            parser.error(
                'Writer method not supported! Please use "api" or "db".'
            )

    return args


def process_pxid(
    px_accessions: list[str],
    temp_dir: str,
    writer_method: str,
    dontdelete: bool,
) -> None:
    """Process ProteomeXchange accessions."""
    for px_accession in px_accessions:
        convert_pxd_accession_from_pride(
            px_accession, temp_dir, writer_method, dontdelete
        )


def process_ftp(
    ftp_url: str,
    temp_dir: str,
    project_identifier: str | None,
    writer_method: str,
    dontdelete: bool,
) -> None:
    """Process data from an FTP URL."""
    if not project_identifier:
        project_identifier = urlparse(ftp_url).path.rsplit("/", 1)[-1]
    convert_from_ftp(
        ftp_url, temp_dir, project_identifier, writer_method, dontdelete
    )


def process_dir(
    local_dir: str,
    project_identifier: str | None,
    writer_method: str,
    nopeaklist: bool,
) -> None:
    """Process data from a local directory."""
    if not project_identifier:
        project_identifier = local_dir.rsplit("/", 1)[-1]
    convert_dir(
        local_dir, project_identifier, writer_method, nopeaklist=nopeaklist
    )


def validate(validate_arg: str, temp_dir: str, nopeaklist: bool) -> None:
    """Validate mzIdentML files against XSD schema and check for other errors.

    This includes checking that Seq elements are present for target proteins,
    even though omitting them is technically valid. Prints results and exits.

    Args:
        validate_arg: Path to the mzIdentML file or directory to validate.
        temp_dir: Temporary directory for validation (SQLite DB created here).
        nopeaklist: If True, skip peaklist file validation.
    """
    if os.path.isdir(validate_arg):
        print(f"Validating directory: {validate_arg}")
        for file in os.listdir(validate_arg):
            if file.endswith(".mzid"):
                file_to_validate = os.path.join(validate_arg, file)
                if validate_file(
                    file_to_validate, temp_dir, nopeaklist=nopeaklist
                ):
                    print(
                        f"Validation successful for file {file_to_validate}."
                    )
                else:
                    print(
                        f"Validation failed for file {file_to_validate}. Exiting."
                    )
                    sys.exit(1)
        print(
            f"SUCCESS! Directory {validate_arg} validation complete. Exciting."
        )
    else:
        if not validate_file(validate_arg, temp_dir, nopeaklist=nopeaklist):
            print(f"Validation failed for file {validate_arg}. Exiting.")
            sys.exit(1)
        print(f"SUCCESS! File {validate_arg} validation complete. Exciting.")

    sys.exit(0)


def json_sequences_and_residue_pairs(filepath: str, temp_dir: str) -> bytes:
    """Return JSON of sequences and residue pairs from mzIdentML files.

    Args:
        filepath: Path to the mzIdentML file or directory to process.
        temp_dir: Temporary directory for SQLite DB (or default if not given).

    Returns:
        JSON-encoded bytes of sequences and residue pairs.
    """
    return orjson.dumps(sequences_and_residue_pairs(filepath, temp_dir))


def sequences_and_residue_pairs(filepath: str, temp_dir: str) -> dict:
    """Return sequences and residue pairs from mzIdentML files as a dictionary.

    Args:
        filepath: Path to the mzIdentML file or directory to process.
        temp_dir: Temporary directory for the SQLite database.

    Returns:
        Dictionary with 'sequences' and 'residue_pairs' keys.
    """
    file = os.path.basename(filepath)
    conn_str = _create_temp_database(temp_dir, file)
    engine = create_engine(conn_str)

    if os.path.isdir(filepath):
        mzid_count = 0
        for file in os.listdir(filepath):
            if file.endswith(".mzid"):
                mzid_count += 1
                file_to_process = os.path.join(filepath, file)
                read_sequences_and_residue_pairs(
                    file_to_process, mzid_count, conn_str
                )
    elif os.path.isfile(filepath):
        if filepath.endswith(".mzid"):
            read_sequences_and_residue_pairs(filepath, 0, conn_str)
        else:
            raise ValueError(
                f'Invalid file path (must end ".mzid"): {filepath}'
            )
    else:
        raise ValueError(f"Invalid file or directory path: {filepath}")

    with engine.connect() as conn:
        # get sequences
        sql = text(
            """
            SELECT dbseq.id, u.identification_file_name as file, dbseq.sequence, dbseq.accession
            FROM upload AS u
            JOIN dbsequence AS dbseq ON u.id = dbseq.upload_id
            INNER JOIN peptideevidence pe ON dbseq.id = pe.dbsequence_id AND dbseq.upload_id = pe.upload_id
            WHERE pe.is_decoy = false
            GROUP BY dbseq.id, dbseq.sequence, dbseq.accession, u.identification_file_name;
            """
        )
        rs = conn.execute(sql)
        seq_rows = rs.mappings().all()
        seq_rows = [dict(row) for row in seq_rows]
        logging.info("Successfully fetched sequences")

        # get residue pairs
        sql = text(
            """SELECT group_concat(si.id) as match_ids, group_concat(u.identification_file_name) as files,
            pe1.dbsequence_id as prot1, dbs1.accession as prot1_acc, (pe1.pep_start + mp1.link_site1 - 1) as pos1,
            pe2.dbsequence_id as prot2, dbs2.accession as prot2_acc, (pe2.pep_start + mp2.link_site1 - 1) as pos2,
			coalesce (mp1.mod_accessions, mp2.mod_accessions) as mod_accs
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
            ;"""
        )
        # note that using pos1 and pos2 in group by won't work in postgres
        start_time = time.time()
        rs = conn.execute(sql)
        elapsed_time = time.time() - start_time
        logging.info(f"residue pair SQL execution time: {elapsed_time}")
        rp_rows = rs.mappings().all()
        rp_rows = [dict(row) for row in rp_rows]
    # Extract database path from connection string and remove it
    temp_database = conn_str.replace("sqlite:///", "")
    os.remove(temp_database)
    return {"sequences": seq_rows, "residue_pairs": rp_rows}


def main() -> None:
    """Execute script logic based on command-line arguments."""
    args = parse_arguments()
    temp_dir = (
        os.path.expanduser(args.temp) if args.temp else tempfile.gettempdir()
    )
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    writer_type = args.writer if args.writer else "db"

    try:
        if args.pxid:
            process_pxid(args.pxid, temp_dir, writer_type, args.dontdelete)
        elif args.ftp:
            process_ftp(
                args.ftp,
                temp_dir,
                args.identifier,
                writer_type,
                args.dontdelete,
            )
        elif args.dir:
            process_dir(
                args.dir, args.identifier, writer_type, args.nopeaklist
            )
        elif args.validate:
            validate(args.validate, temp_dir, args.nopeaklist)
        elif args.seqsandresiduepairs:
            json_data = json_sequences_and_residue_pairs(
                args.seqsandresiduepairs, temp_dir
            )
            with open(args.json, "w") as f:
                f.write(json_data.decode("utf-8"))
        sys.exit(0)
    except Exception as ex:
        logger.error(ex)
        traceback.print_exc()
        sys.exit(1)


def convert_pxd_accession(
    px_accession: str, temp_dir: str, writer_method: str, dontdelete: bool
) -> None:
    """Get FTP location from ProteomeXchange and process dataset."""
    px_url = f"https://proteomecentral.proteomexchange.org/cgi/GetDataset?ID={px_accession}&outputMode=JSON"
    logger.info(f"GET request to ProteomeExchange: {px_url}")
    px_response = requests.get(px_url, timeout=30)

    if px_response.status_code == 200:
        logger.info("ProteomeExchange returned status code 200")
        px_json = px_response.json()
        ftp_url = None
        for dataSetLink in px_json["fullDatasetLinks"]:
            # name check is necessary because some things have wrong acc, e.g. PXD006574
            if (
                dataSetLink["accession"] == "MS:1002852"
                or dataSetLink["name"] == "Dataset FTP location"
            ):
                ftp_url = dataSetLink["value"]
                convert_from_ftp(
                    ftp_url, temp_dir, px_accession, writer_method, dontdelete
                )
                break
        if not ftp_url:
            raise ValueError(
                "Dataset FTP location not found in ProteomeXchange response"
            )
    else:
        raise ValueError(
            f"ProteomeXchange returned status code {px_response.status_code}"
        )


def convert_pxd_accession_from_pride(
    px_accession: str, temp_dir: str, writer_method: str, dontdelete: bool
) -> None:
    """Get FTP location from PRIDE API and process dataset."""
    px_url = f"https://www.ebi.ac.uk/pride/ws/archive/v3/projects/{px_accession}/files"
    logger.info(f"GET request to PRIDE API: {px_url}")
    pride_response = requests.get(px_url, timeout=30)

    if pride_response.status_code == 200:
        logger.info("PRIDE API returned status code 200")
        pride_json = pride_response.json()
        ftp_url = None

        if pride_json:
            for protocol in pride_json[0].get("publicFileLocations", []):
                if protocol["name"] == "FTP Protocol":
                    parsed_url = urlparse(protocol["value"])
                    parent_folder = (
                        f"{parsed_url.scheme}://{parsed_url.netloc}"
                        + "/".join(parsed_url.path.split("/")[:-1])
                    )
                    logger.info(f"PRIDE FTP path : {parent_folder}")
                    ftp_url = parent_folder
                    break
        if ftp_url:
            convert_from_ftp(
                ftp_url, temp_dir, px_accession, writer_method, dontdelete
            )
        else:
            raise ValueError(
                "Public File location not found in PRIDE API response"
            )
    else:
        raise ValueError(
            f"PRIDE API returned status code {pride_response.status_code}"
        )


def convert_from_ftp(
    ftp_url: str,
    temp_dir: str,
    project_identifier: str,
    writer_method: str,
    dontdelete: bool,
) -> None:
    """Download and convert data from an FTP URL."""
    if not ftp_url.startswith("ftp://"):
        raise ValueError("FTP location must start with ftp://")

    # Create temp directory if not exists
    os.makedirs(temp_dir, exist_ok=True)
    logger.info(f"FTP url: {ftp_url}")

    path = os.path.join(temp_dir, project_identifier)
    os.makedirs(path, exist_ok=True)

    ftp_ip = socket.getaddrinfo(urlparse(ftp_url).hostname, 21)[0][4][0]
    files = get_ftp_file_list(ftp_ip, urlparse(ftp_url).path)
    for f in files:
        f_lower = f.lower()
        if not (
            os.path.isfile(os.path.join(str(path), f))
            or f_lower in SKIP_DIRS
            or f_lower.endswith(SKIP_EXTENSIONS)
        ):
            logger.info(f"Downloading {f} to {path}")
            ftp = get_ftp_login(ftp_ip)
            try:
                ftp.cwd(urlparse(ftp_url).path)
                with open(os.path.join(str(path), f), "wb") as file:
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
            logger.error(f"Failed to delete temp directory {path}")
            raise e


def get_ftp_login(ftp_ip: str) -> ftplib.FTP:
    """Log in to an FTP server."""
    while True:
        time.sleep(10)  # Delay to avoid rate limiting
        try:
            ftp = ftplib.FTP(ftp_ip)
            ftp.login()  # Uses password: anonymous@
            return ftp
        except ftplib.all_errors as e:
            logger.error(f'FTP login failed at {time.strftime("%c")}')


def get_ftp_file_list(ftp_ip: str, ftp_dir: str) -> list[str]:
    """Get a list of files from an FTP directory."""
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


def convert_dir(
    local_dir: str,
    project_identifier: str,
    writer_method: str,
    nopeaklist: bool = False,
) -> None:
    """Convert files in a local directory."""
    peaklist_dir = None if nopeaklist else local_dir
    for file in os.listdir(local_dir):
        gc.collect()
        if file.endswith((".mzid", ".mzid.gz")):
            logger.info(f"Processing {file}")
            conn_str = get_conn_str()
            if writer_method.lower() == "api":
                writer = APIWriter(pxid=project_identifier)
            else:
                writer = DatabaseWriter(conn_str, pxid=project_identifier)
            # if schema_validate(os.path.join(local_dir, file)):
            id_parser = MzIdParser(
                os.path.join(local_dir, file),
                peaklist_dir,
                writer,
                logger,
            )
            try:
                id_parser.parse()
                # logger.info(id_parser.warnings + "\n")
            except Exception as e:
                logger.error(f"Error parsing {file}")
                logger.exception(e)
                raise e
            finally:
                _dispose_writer_engine(writer)
            # else:
            #     print(f"File {file} is schema invalid.")
            #     sys.exit(1)


def validate_file(
    filepath: str, temp_dir: str, nopeaklist: bool = False
) -> bool:
    """Validate mzIdentML file against 1.2.0 or 1.3.0 schema and check for other errors.

    Args:
        filepath: Path to the mzIdentML file to validate.
        temp_dir: Temporary directory for validation (SQLite DB created here).
        nopeaklist: If True, skip peaklist file validation (default: False).

    Returns:
        True if the file is valid, False otherwise.
    """
    print(f"Validating file {filepath}.")

    local_dir = os.path.dirname(filepath)
    file = os.path.basename(filepath)
    peaklist_dir = None if nopeaklist else local_dir

    if not file.endswith(".mzid"):
        raise ValueError(f'Invalid file path (must end ".mzid"): {filepath}')

    if schema_validate(filepath):
        print(f"File {filepath} is schema valid.")

        conn_str = _create_temp_database(temp_dir, file)
        engine = create_engine(conn_str)
        test_database = conn_str.replace("sqlite:///", "")

        # switch on Foreign Key Enforcement
        with engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON;"))

        writer = DatabaseWriter(conn_str, upload_id=1, pxid="Validation")
        id_parser = SqliteMzIdParser(
            os.path.join(local_dir, file),
            peaklist_dir,
            writer,
            logger,
        )
        try:
            id_parser.parse()
            os.remove(test_database)
        except Exception as e:
            print(f"Error parsing {filepath}")
            print(e)
            return False
        finally:
            _dispose_writer_engine(writer)

    else:
        print(f"File {filepath} is schema invalid.")
        return False

    return True


def read_sequences_and_residue_pairs(
    filepath: str, upload_id: int, conn_str: str
) -> None:
    """Get sequences and residue pairs from mzIdentML files.

    Args:
        filepath: Path to the mzIdentML file to process.
        upload_id: Upload ID to use for sequences and residue pairs.
        conn_str: Connection string for the SQLite database.
    """
    writer = DatabaseWriter(conn_str, upload_id, pxid="Validation")
    id_parser = SqliteMzIdParser(filepath, None, writer, logger)
    try:
        id_parser.parse()
    except Exception as e:
        print(f"Error parsing {filepath}")
        raise e
    finally:
        _dispose_writer_engine(writer)


if __name__ == "__main__":
    main()

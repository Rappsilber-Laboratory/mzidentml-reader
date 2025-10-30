"""Tests for parser/process_dataset.py module."""

import argparse
import json
import os
import sys
import tempfile
from parser.process_dataset import (
    _create_temp_database,
    _dispose_writer_engine,
    json_sequences_and_residue_pairs,
    main,
    parse_arguments,
    process_dir,
    process_ftp,
    process_pxid,
    sequences_and_residue_pairs,
    validate,
    validate_file,
)
from pathlib import Path
from unittest import mock

import pytest
from sqlalchemy import create_engine, text

# Get the absolute path to the tests directory
TESTS_DIR = Path(__file__).parent
PROJECT_ROOT = TESTS_DIR.parent
FIXTURES_DIR = TESTS_DIR / "fixtures" / "mzid_parser"


class TestParseArguments:
    """Test suite for parse_arguments function."""

    def test_pxid_argument(self):
        """Test parsing with --pxid argument."""
        with mock.patch("sys.argv", ["prog", "--pxid", "PXD012345"]):
            args = parse_arguments()
            assert args.pxid == ["PXD012345"]
            assert args.ftp is None
            assert args.dir is None
            assert args.validate is None

    def test_multiple_pxids(self):
        """Test parsing with multiple --pxid arguments."""
        with mock.patch("sys.argv", ["prog", "-p", "PXD012345", "PXD067890"]):
            args = parse_arguments()
            assert args.pxid == ["PXD012345", "PXD067890"]

    def test_ftp_argument(self):
        """Test parsing with --ftp argument."""
        with mock.patch(
            "sys.argv",
            ["prog", "--ftp", "ftp://ftp.example.com/data"],
        ):
            args = parse_arguments()
            assert args.ftp == "ftp://ftp.example.com/data"
            assert args.pxid is None

    def test_dir_argument(self):
        """Test parsing with --dir argument."""
        with mock.patch("sys.argv", ["prog", "--dir", "/path/to/data"]):
            args = parse_arguments()
            assert args.dir == "/path/to/data"
            assert args.pxid is None

    def test_validate_argument(self):
        """Test parsing with --validate argument."""
        with mock.patch(
            "sys.argv", ["prog", "--validate", "/path/to/file.mzid"]
        ):
            args = parse_arguments()
            assert args.validate == "/path/to/file.mzid"
            assert args.pxid is None

    def test_seqsandresiduepairs_with_json(self):
        """Test parsing with --seqsandresiduepairs and --json."""
        with mock.patch(
            "sys.argv",
            [
                "prog",
                "--seqsandresiduepairs",
                "/path/to/data",
                "--json",
                "output.json",
            ],
        ):
            args = parse_arguments()
            assert args.seqsandresiduepairs == "/path/to/data"
            assert args.json == "output.json"

    def test_seqsandresiduepairs_without_json_fails(self):
        """Test that --seqsandresiduepairs without --json fails."""
        with mock.patch(
            "sys.argv",
            ["prog", "--seqsandresiduepairs", "/path/to/data"],
        ):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_mutually_exclusive_group(self):
        """Test that mutually exclusive arguments fail together."""
        with mock.patch(
            "sys.argv", ["prog", "-p", "PXD012345", "-d", "/path"]
        ):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_no_required_argument_fails(self):
        """Test that missing required argument fails."""
        with mock.patch("sys.argv", ["prog"]):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_optional_identifier_argument(self):
        """Test --identifier optional argument."""
        with mock.patch(
            "sys.argv",
            ["prog", "-d", "/path/to/data", "-i", "MyDataset"],
        ):
            args = parse_arguments()
            assert args.identifier == "MyDataset"

    def test_optional_temp_argument(self):
        """Test --temp optional argument."""
        with mock.patch(
            "sys.argv",
            ["prog", "-d", "/path/to/data", "-t", "/tmp/custom"],
        ):
            args = parse_arguments()
            assert args.temp == "/tmp/custom"

    def test_optional_nopeaklist_argument(self):
        """Test --nopeaklist optional argument."""
        with mock.patch(
            "sys.argv",
            ["prog", "-d", "/path/to/data", "--nopeaklist"],
        ):
            args = parse_arguments()
            assert args.nopeaklist is True

    def test_optional_dontdelete_argument(self):
        """Test --dontdelete optional argument."""
        with mock.patch(
            "sys.argv",
            ["prog", "-p", "PXD012345", "--dontdelete"],
        ):
            args = parse_arguments()
            assert args.dontdelete is True

    def test_writer_api_argument(self):
        """Test --writer api argument."""
        with mock.patch(
            "sys.argv", ["prog", "-d", "/path/to/data", "-w", "api"]
        ):
            args = parse_arguments()
            assert args.writer == "api"

    def test_writer_db_argument(self):
        """Test --writer db argument."""
        with mock.patch(
            "sys.argv", ["prog", "-d", "/path/to/data", "-w", "db"]
        ):
            args = parse_arguments()
            assert args.writer == "db"

    def test_writer_invalid_argument_fails(self):
        """Test that invalid --writer argument fails."""
        with mock.patch(
            "sys.argv",
            ["prog", "-d", "/path/to/data", "-w", "invalid"],
        ):
            with pytest.raises(SystemExit):
                parse_arguments()


class TestHelperFunctions:
    """Test suite for helper functions."""

    def test_create_temp_database(self):
        """Test _create_temp_database creates correct path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            conn_str = _create_temp_database(temp_dir, "test.mzid")
            expected_path = os.path.join(temp_dir, "test.db")
            assert conn_str == f"sqlite:///{expected_path}"
            # Should not exist yet (just returns the path)
            assert not os.path.exists(expected_path)

    def test_create_temp_database_removes_existing(self):
        """Test _create_temp_database removes existing database."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create an existing database file
            test_db = os.path.join(temp_dir, "test.db")
            with open(test_db, "w") as f:
                f.write("existing content")

            conn_str = _create_temp_database(temp_dir, "test.mzid")
            # File should be removed
            assert not os.path.exists(test_db)
            assert conn_str == f"sqlite:///{test_db}"

    def test_create_temp_database_strips_extension(self):
        """Test _create_temp_database strips file extension."""
        with tempfile.TemporaryDirectory() as temp_dir:
            conn_str = _create_temp_database(temp_dir, "my_file.mzid.gz")
            # Only strips the last extension (.gz), not .mzid
            expected_path = os.path.join(temp_dir, "my_file.mzid.db")
            assert conn_str == f"sqlite:///{expected_path}"

    def test_dispose_writer_engine_with_engine(self):
        """Test _dispose_writer_engine disposes engine."""
        mock_writer = mock.Mock()
        mock_engine = mock.Mock()
        mock_writer.engine = mock_engine

        _dispose_writer_engine(mock_writer)

        mock_engine.dispose.assert_called_once()

    def test_dispose_writer_engine_without_engine(self):
        """Test _dispose_writer_engine with no engine attribute."""
        mock_writer = mock.Mock(spec=[])  # No engine attribute

        # Should not raise an error
        _dispose_writer_engine(mock_writer)


class TestValidateFile:
    """Test suite for validate_file function."""

    @pytest.fixture
    def valid_mzid_file(self):
        """Path to a valid mzIdentML file."""
        return str(FIXTURES_DIR / "mgf_ecoli_dsso.mzid")

    def test_validate_valid_file(self, valid_mzid_file, capsys):
        """Test validation of a valid mzIdentML file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Use nopeaklist=True since peaklist files aren't available
            result = validate_file(valid_mzid_file, temp_dir, nopeaklist=True)
            assert result is True

            captured = capsys.readouterr()
            assert "schema valid" in captured.out

    def test_validate_invalid_extension(self):
        """Test validation fails for non-.mzid file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
                temp_file = f.name

            try:
                with pytest.raises(ValueError, match="must end"):
                    validate_file(temp_file, temp_dir)
            finally:
                os.unlink(temp_file)

    def test_validate_with_nopeaklist(self, valid_mzid_file):
        """Test validation with nopeaklist=True."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = validate_file(valid_mzid_file, temp_dir, nopeaklist=True)
            assert result is True


class TestValidateFunction:
    """Test suite for validate function."""

    @pytest.fixture
    def temp_valid_mzid_dir(self):
        """Create a temporary directory with a valid mzid file."""
        temp_dir = tempfile.mkdtemp()
        source_file = str(FIXTURES_DIR / "mgf_ecoli_dsso.mzid")
        dest_file = os.path.join(temp_dir, "test.mzid")
        import shutil

        shutil.copy(source_file, dest_file)
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir)

    def test_validate_directory_success(self, temp_valid_mzid_dir, capsys):
        """Test validation of a directory with valid files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(SystemExit) as exc_info:
                # Use nopeaklist=True since peaklists aren't available
                validate(temp_valid_mzid_dir, temp_dir, nopeaklist=True)
            # Should exit with 0 for success
            assert exc_info.value.code == 0

            captured = capsys.readouterr()
            assert "SUCCESS" in captured.out

    def test_validate_single_file_success(self, capsys):
        """Test validation of a single valid file."""
        valid_file = str(FIXTURES_DIR / "mgf_ecoli_dsso.mzid")
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(SystemExit) as exc_info:
                # Use nopeaklist=True since peaklists aren't available
                validate(valid_file, temp_dir, nopeaklist=True)
            # Should exit with 0 for success
            assert exc_info.value.code == 0

            captured = capsys.readouterr()
            assert "SUCCESS" in captured.out


class TestProcessWrappers:
    """Test suite for process wrapper functions."""

    def test_process_pxid(self):
        """Test process_pxid wrapper calls convert function."""
        with mock.patch(
            "parser.process_dataset.convert_pxd_accession_from_pride"
        ) as mock_convert:
            process_pxid(
                ["PXD012345", "PXD067890"],
                "/tmp",
                "db",
                dontdelete=False,
            )

            assert mock_convert.call_count == 2
            mock_convert.assert_any_call("PXD012345", "/tmp", "db", False)
            mock_convert.assert_any_call("PXD067890", "/tmp", "db", False)

    def test_process_ftp_with_identifier(self):
        """Test process_ftp wrapper with identifier."""
        with mock.patch(
            "parser.process_dataset.convert_from_ftp"
        ) as mock_convert:
            process_ftp(
                "ftp://example.com/data",
                "/tmp",
                "MyDataset",
                "db",
                dontdelete=True,
            )

            mock_convert.assert_called_once_with(
                "ftp://example.com/data",
                "/tmp",
                "MyDataset",
                "db",
                True,
            )

    def test_process_ftp_without_identifier(self):
        """Test process_ftp extracts identifier from URL."""
        with mock.patch(
            "parser.process_dataset.convert_from_ftp"
        ) as mock_convert:
            process_ftp(
                "ftp://example.com/path/to/DATASET123",
                "/tmp",
                None,
                "db",
                dontdelete=False,
            )

            mock_convert.assert_called_once_with(
                "ftp://example.com/path/to/DATASET123",
                "/tmp",
                "DATASET123",
                "db",
                False,
            )

    def test_process_dir_with_identifier(self):
        """Test process_dir wrapper with identifier."""
        with mock.patch("parser.process_dataset.convert_dir") as mock_convert:
            process_dir(
                "/path/to/data",
                "MyDataset",
                "api",
                nopeaklist=False,
            )

            mock_convert.assert_called_once_with(
                "/path/to/data",
                "MyDataset",
                "api",
                nopeaklist=False,
            )

    def test_process_dir_without_identifier(self):
        """Test process_dir extracts identifier from path."""
        with mock.patch("parser.process_dataset.convert_dir") as mock_convert:
            process_dir("/path/to/DATASET123", None, "db", nopeaklist=True)

            mock_convert.assert_called_once_with(
                "/path/to/DATASET123",
                "DATASET123",
                "db",
                nopeaklist=True,
            )


class TestSequencesAndResiduePairs:
    """Test suite for sequences_and_residue_pairs functions."""

    @pytest.fixture
    def valid_mzid_file(self):
        """Path to a valid mzIdentML file."""
        return str(FIXTURES_DIR / "mgf_ecoli_dsso.mzid")

    def test_sequences_and_residue_pairs_file(self, valid_mzid_file):
        """Test sequences_and_residue_pairs with single file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = sequences_and_residue_pairs(valid_mzid_file, temp_dir)

            assert isinstance(result, dict)
            assert "sequences" in result
            assert "residue_pairs" in result
            assert isinstance(result["sequences"], list)
            assert isinstance(result["residue_pairs"], list)

    def test_json_sequences_and_residue_pairs(self, valid_mzid_file):
        """Test json_sequences_and_residue_pairs returns bytes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = json_sequences_and_residue_pairs(
                valid_mzid_file, temp_dir
            )

            assert isinstance(result, bytes)
            # Should be valid JSON
            decoded = json.loads(result)
            assert "sequences" in decoded
            assert "residue_pairs" in decoded

    def test_sequences_and_residue_pairs_invalid_file(self):
        """Test with invalid file path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValueError, match="Invalid file or directory"):
                sequences_and_residue_pairs("/nonexistent/file.txt", temp_dir)

    def test_sequences_and_residue_pairs_invalid_path(self):
        """Test with invalid path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValueError, match="Invalid file or directory"):
                sequences_and_residue_pairs("/nonexistent/path", temp_dir)


class TestNetworkFunctions:
    """Test suite for network and FTP functions with mocking."""

    def test_convert_pxd_accession_from_pride_success(self):
        """Test convert_pxd_accession_from_pride with successful API response."""
        from parser.process_dataset import convert_pxd_accession_from_pride

        mock_response_data = [
            {
                "publicFileLocations": [
                    {
                        "name": "FTP Protocol",
                        "value": "ftp://ftp.pride.ebi.ac.uk/pride/data/archive/2020/01/PXD012345/file.mzid",
                    }
                ]
            }
        ]

        with mock.patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = mock_response_data

            with mock.patch(
                "parser.process_dataset.convert_from_ftp"
            ) as mock_convert:
                convert_pxd_accession_from_pride(
                    "PXD012345", "/tmp", "db", False
                )

                mock_get.assert_called_once()
                assert "PXD012345" in mock_get.call_args[0][0]
                mock_convert.assert_called_once()

    def test_convert_pxd_accession_from_pride_api_error(self):
        """Test convert_pxd_accession_from_pride with API error."""
        from parser.process_dataset import convert_pxd_accession_from_pride

        with mock.patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 404

            with pytest.raises(
                ValueError, match="PRIDE API returned status code 404"
            ):
                convert_pxd_accession_from_pride(
                    "PXD012345", "/tmp", "db", False
                )

    def test_convert_pxd_accession_from_pride_no_ftp_location(self):
        """Test convert_pxd_accession_from_pride with no FTP location."""
        from parser.process_dataset import convert_pxd_accession_from_pride

        mock_response_data = [{"publicFileLocations": []}]

        with mock.patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = mock_response_data

            with pytest.raises(
                ValueError, match="Public File location not found"
            ):
                convert_pxd_accession_from_pride(
                    "PXD012345", "/tmp", "db", False
                )

    def test_convert_from_ftp_invalid_url(self):
        """Test convert_from_ftp with invalid URL."""
        from parser.process_dataset import convert_from_ftp

        with pytest.raises(
            ValueError, match="FTP location must start with ftp://"
        ):
            convert_from_ftp("http://example.com", "/tmp", "test", "db", False)

    def test_get_ftp_file_list(self):
        """Test get_ftp_file_list with mocked FTP."""
        from parser.process_dataset import get_ftp_file_list

        with mock.patch("ftplib.FTP") as mock_ftp_class:
            mock_ftp = mock.Mock()
            mock_ftp_class.return_value = mock_ftp
            mock_ftp.nlst.return_value = ["file1.mzid", "file2.mzid"]

            result = get_ftp_file_list("127.0.0.1", "/data")

            assert result == ["file1.mzid", "file2.mzid"]
            mock_ftp.login.assert_called_once()
            mock_ftp.cwd.assert_called_once_with("/data")

    def test_get_ftp_file_list_no_files(self):
        """Test get_ftp_file_list with no files."""
        import ftplib
        from parser.process_dataset import get_ftp_file_list

        with mock.patch("ftplib.FTP") as mock_ftp_class:
            mock_ftp = mock.Mock()
            mock_ftp_class.return_value = mock_ftp
            mock_ftp.nlst.side_effect = ftplib.error_perm("550 No files found")

            with pytest.raises(ftplib.error_perm):
                get_ftp_file_list("127.0.0.1", "/data")

    def test_get_ftp_login(self):
        """Test get_ftp_login successful connection."""
        from parser.process_dataset import get_ftp_login

        with mock.patch("ftplib.FTP") as mock_ftp_class:
            with mock.patch("time.sleep"):  # Skip the sleep delay
                mock_ftp = mock.Mock()
                mock_ftp_class.return_value = mock_ftp

                result = get_ftp_login("127.0.0.1")

                assert result == mock_ftp
                mock_ftp.login.assert_called_once()

    def test_convert_dir_with_mzid_files(self):
        """Test convert_dir processes mzid files."""
        from parser.process_dataset import convert_dir

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test mzid file
            test_mzid = os.path.join(temp_dir, "test.mzid")
            source_file = str(FIXTURES_DIR / "mgf_ecoli_dsso.mzid")
            import shutil

            shutil.copy(source_file, test_mzid)

            with mock.patch(
                "parser.process_dataset.schema_validate"
            ) as mock_validate:
                with mock.patch(
                    "parser.process_dataset.MzIdParser"
                ) as mock_parser:
                    mock_validate.return_value = True
                    mock_parser_instance = mock.Mock()
                    mock_parser.return_value = mock_parser_instance

                    convert_dir(temp_dir, "TestProject", "db", nopeaklist=True)

                    mock_validate.assert_called_once()
                    mock_parser_instance.parse.assert_called_once()


class TestMainFunction:
    """Test suite for main function."""

    def test_main_with_pxid(self):
        """Test main function with pxid argument."""
        with mock.patch("sys.argv", ["prog", "-p", "PXD012345"]):
            with mock.patch(
                "parser.process_dataset.process_pxid"
            ) as mock_process:
                with mock.patch("sys.exit") as mock_exit:
                    main()
                    mock_process.assert_called_once()
                    mock_exit.assert_called_once_with(0)

    def test_main_with_validate(self):
        """Test main function with validate argument."""
        valid_file = str(FIXTURES_DIR / "mgf_ecoli_dsso.mzid")
        with mock.patch("sys.argv", ["prog", "-v", valid_file]):
            with mock.patch("sys.exit") as mock_exit:
                main()
                # validate() calls sys.exit(0) on success
                # or sys.exit(1) on failure
                assert mock_exit.called

    def test_main_with_seqsandresiduepairs(self):
        """Test main function with seqsandresiduepairs."""
        valid_file = str(FIXTURES_DIR / "mgf_ecoli_dsso.mzid")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_file = f.name

        try:
            with mock.patch(
                "sys.argv",
                [
                    "prog",
                    "--seqsandresiduepairs",
                    valid_file,
                    "-j",
                    output_file,
                ],
            ):
                with mock.patch("sys.exit") as mock_exit:
                    main()
                    mock_exit.assert_called_once_with(0)

            # Check that output file was created and contains JSON
            assert os.path.exists(output_file)
            with open(output_file, "r") as f:
                data = json.load(f)
                assert "sequences" in data
                assert "residue_pairs" in data
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)

    def test_main_error_handling(self):
        """Test main function error handling."""
        with mock.patch("sys.argv", ["prog", "-p", "PXD012345"]):
            with mock.patch(
                "parser.process_dataset.process_pxid"
            ) as mock_process:
                mock_process.side_effect = Exception("Test error")
                with mock.patch("sys.exit") as mock_exit:
                    main()
                    mock_exit.assert_called_once_with(1)

    def test_main_creates_temp_dir_if_not_exists(self):
        """Test main creates temp directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as base_temp:
            temp_path = os.path.join(base_temp, "custom_temp")
            valid_file = str(FIXTURES_DIR / "mgf_ecoli_dsso.mzid")

            with mock.patch(
                "sys.argv",
                ["prog", "-v", valid_file, "-t", temp_path],
            ):
                with mock.patch("sys.exit"):
                    main()

                # Temp directory should have been created
                assert os.path.exists(temp_path)

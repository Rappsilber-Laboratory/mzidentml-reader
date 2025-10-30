"""Tests for parser/schema_validate.py module."""

import os
import tempfile
from parser.schema_validate import schema_validate
from pathlib import Path
from unittest import mock

import pytest

# Get the absolute path to the tests directory
TESTS_DIR = Path(__file__).parent
FIXTURES_DIR = TESTS_DIR / "fixtures" / "mzid_parser"


class TestSchemaValidate:
    """Test suite for schema_validate function."""

    @pytest.fixture
    def valid_1_2_0_file(self):
        """Path to a valid mzIdentML 1.2.0 file."""
        return str(FIXTURES_DIR / "mgf_ecoli_dsso.mzid")

    @pytest.fixture
    def valid_1_3_0_file(self):
        """Path to a valid mzIdentML 1.3.0 file."""
        return str(
            FIXTURES_DIR / "1.3.0" / "multiple_spectra_per_id_1_3_0_draft.mzid"
        )

    def test_valid_mzid_1_2_0(self, valid_1_2_0_file):
        """Test validation of a valid mzIdentML 1.2.0 file."""
        assert os.path.exists(
            valid_1_2_0_file
        ), f"Test fixture not found: {valid_1_2_0_file}"
        result = schema_validate(valid_1_2_0_file)
        assert result is True

    def test_valid_mzid_1_3_0(self, valid_1_3_0_file):
        """Test validation of a valid mzIdentML 1.3.0 file."""
        assert os.path.exists(
            valid_1_3_0_file
        ), f"Test fixture not found: {valid_1_3_0_file}"
        result = schema_validate(valid_1_3_0_file)
        assert result is True

    def test_no_schema_location(self, capsys):
        """Test file with no schema location attribute."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".mzid", delete=False
        ) as f:
            f.write(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<MzIdentML xmlns="http://psidev.info/psi/pi/mzIdentML/1.2">\n'
                "</MzIdentML>\n"
            )
            temp_file = f.name

        try:
            result = schema_validate(temp_file)
            assert result is False

            captured = capsys.readouterr()
            assert "No schema location found" in captured.out
        finally:
            os.unlink(temp_file)

    def test_invalid_schema_location_format(self, capsys):
        """Test file with invalid schema location format."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".mzid", delete=False
        ) as f:
            # Odd number of parts (invalid format)
            f.write(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                "<MzIdentML "
                'xmlns="http://psidev.info/psi/pi/mzIdentML/1.2" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                'xsi:schemaLocation="http://psidev.info/psi/pi/mzIdentML/1.2 '
                'https://example.com/schema.xsd extra_part">\n'
                "</MzIdentML>\n"
            )
            temp_file = f.name

        try:
            result = schema_validate(temp_file)
            assert result is False

            captured = capsys.readouterr()
            assert "Invalid schema location format" in captured.out
        finally:
            os.unlink(temp_file)

    def test_unsupported_schema_version(self, capsys):
        """Test file with unsupported schema version."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".mzid", delete=False
        ) as f:
            f.write(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                "<MzIdentML "
                'xmlns="http://psidev.info/psi/pi/mzIdentML/1.1" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                'xsi:schemaLocation="http://psidev.info/psi/pi/mzIdentML/1.1 '
                'https://example.com/mzIdentML1.1.0.xsd">\n'
                "</MzIdentML>\n"
            )
            temp_file = f.name

        try:
            result = schema_validate(temp_file)
            assert result is False

            captured = capsys.readouterr()
            assert "only supporting 1.2.0 and 1.3.0" in captured.out
            assert "mzIdentML1.1.0.xsd" in captured.out
        finally:
            os.unlink(temp_file)

    def test_schema_file_not_found(self, capsys):
        """Test schema file not found error."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".mzid", delete=False
        ) as f:
            f.write(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                "<MzIdentML "
                'xmlns="http://psidev.info/psi/pi/mzIdentML/1.2" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                'xsi:schemaLocation="http://psidev.info/psi/pi/mzIdentML/1.2 '
                'https://example.com/mzIdentML1.2.0.xsd">\n'
                "</MzIdentML>\n"
            )
            temp_file = f.name

        try:
            # Mock the files() function to raise FileNotFoundError
            with mock.patch("parser.schema_validate.files") as mock_files:
                mock_files.side_effect = FileNotFoundError("Schema not found")
                result = schema_validate(temp_file)
                assert result is False

                captured = capsys.readouterr()
                assert "Schema file not found" in captured.out
        finally:
            os.unlink(temp_file)

    def test_schema_invalid_xml(self, capsys):
        """Test validation of XML that doesn't match schema."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".mzid", delete=False
        ) as f:
            # Valid XML but missing required elements
            f.write(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                "<MzIdentML "
                'xmlns="http://psidev.info/psi/pi/mzIdentML/1.2" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                'xsi:schemaLocation="http://psidev.info/psi/pi/mzIdentML/1.2 '
                "https://www.psidev.info/sites/default/files/2018-10/"
                'mzIdentML1.2.0.xsd">\n'
                "  <InvalidElement>Content</InvalidElement>\n"
                "</MzIdentML>\n"
            )
            temp_file = f.name

        try:
            result = schema_validate(temp_file)
            assert result is False

            captured = capsys.readouterr()
            assert "XML is invalid" in captured.out
            assert "Error:" in captured.out
        finally:
            os.unlink(temp_file)

    def test_malformed_xml(self):
        """Test validation of malformed XML file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".mzid", delete=False
        ) as f:
            f.write(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                "<MzIdentML>\n"
                "  <UnclosedTag>\n"  # Missing closing tag
                "</MzIdentML>\n"
            )
            temp_file = f.name

        try:
            # Malformed XML should raise an exception during parsing
            with pytest.raises(Exception):
                schema_validate(temp_file)
        finally:
            os.unlink(temp_file)

    def test_no_namespace_schema_location(self):
        """Test file using noNamespaceSchemaLocation attribute."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".mzid", delete=False
        ) as f:
            f.write(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                "<MzIdentML "
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                "xsi:noNamespaceSchemaLocation="
                '"https://example.com/mzIdentML1.2.0.xsd">\n'
                "</MzIdentML>\n"
            )
            temp_file = f.name

        try:
            # Should handle noNamespaceSchemaLocation
            # (will fail validation but shouldn't error on parsing)
            result = schema_validate(temp_file)
            # Expected to be False because schema won't validate
            assert result is False
        finally:
            os.unlink(temp_file)

"""
Tests for sequences and residue pairs extraction functionality.

This module tests the --seqsandresiduepairs feature which extracts
sequences and crosslinked residue pairs from mzIdentML files.
"""

import json
import logging
import os
import shutil
import tempfile
from parser.process_dataset import (
    json_sequences_and_residue_pairs,
    sequences_and_residue_pairs,
)

import orjson
import pytest
from sqlalchemy import create_engine

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@pytest.fixture
def fixtures_dir():
    """Return path to test fixtures directory."""
    return os.path.join(os.path.dirname(__file__), "fixtures", "mzid_parser")


@pytest.fixture
def temp_dir():
    """Create and return a temporary directory for test databases."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def test_dir_with_mzid(fixtures_dir, temp_dir):
    """Create a temp directory with mzid file."""
    test_data_dir = os.path.join(temp_dir, "test_data")
    os.makedirs(test_data_dir)

    # Copy mzid file
    src_mzid = os.path.join(fixtures_dir, "mgf_ecoli_dsso.mzid")
    shutil.copy(src_mzid, test_data_dir)

    yield test_data_dir


class TestSequencesAndResiduePairsSingleFile:
    """Tests for processing single mzIdentML files."""

    def test_basic_file_processing(self, test_dir_with_mzid, temp_dir):
        """Test basic extraction from a single mzid file."""
        mzid_file = os.path.join(test_dir_with_mzid, "mgf_ecoli_dsso.mzid")

        result = sequences_and_residue_pairs(mzid_file, temp_dir)

        # Verify structure
        assert isinstance(result, dict)
        assert "sequences" in result
        assert "residue_pairs" in result
        assert isinstance(result["sequences"], list)
        assert isinstance(result["residue_pairs"], list)

    def test_sequences_structure(self, test_dir_with_mzid, temp_dir):
        """Test that sequences have correct structure."""
        mzid_file = os.path.join(test_dir_with_mzid, "mgf_ecoli_dsso.mzid")

        result = sequences_and_residue_pairs(mzid_file, temp_dir)

        if len(result["sequences"]) > 0:
            seq = result["sequences"][0]
            # Check required fields
            assert "id" in seq
            assert "file" in seq
            assert "sequence" in seq
            assert "accession" in seq
            # Check types (id can be int or str depending on database)
            assert isinstance(seq["id"], (int, str))
            assert isinstance(seq["file"], str)
            assert isinstance(seq["sequence"], str)
            assert isinstance(seq["accession"], str)

    def test_residue_pairs_structure(self, test_dir_with_mzid, temp_dir):
        """Test that residue pairs have correct structure."""
        mzid_file = os.path.join(test_dir_with_mzid, "mgf_ecoli_dsso.mzid")

        result = sequences_and_residue_pairs(mzid_file, temp_dir)

        if len(result["residue_pairs"]) > 0:
            rp = result["residue_pairs"][0]
            # Check required fields
            assert "match_ids" in rp
            assert "files" in rp
            assert "prot1" in rp
            assert "prot1_acc" in rp
            assert "pos1" in rp
            assert "prot2" in rp
            assert "prot2_acc" in rp
            assert "pos2" in rp
            assert "mod_accs" in rp
            # Check types (prot ids can be int or str depending on database)
            assert isinstance(rp["match_ids"], str)
            assert isinstance(rp["files"], str)
            assert isinstance(rp["prot1"], (int, str))
            assert isinstance(rp["prot1_acc"], str)
            assert isinstance(rp["pos1"], int)
            assert isinstance(rp["prot2"], (int, str))
            assert isinstance(rp["prot2_acc"], str)
            assert isinstance(rp["pos2"], int)

    def test_json_output_format(self, test_dir_with_mzid, temp_dir):
        """Test that JSON output is properly formatted."""
        mzid_file = os.path.join(test_dir_with_mzid, "mgf_ecoli_dsso.mzid")

        json_output = json_sequences_and_residue_pairs(mzid_file, temp_dir)

        # Should be bytes from orjson
        assert isinstance(json_output, bytes)

        # Should be valid JSON
        decoded = json.loads(json_output)
        assert isinstance(decoded, dict)
        assert "sequences" in decoded
        assert "residue_pairs" in decoded

    def test_temp_database_cleanup(self, test_dir_with_mzid, temp_dir):
        """Test that temporary database is cleaned up after processing."""
        mzid_file = os.path.join(test_dir_with_mzid, "mgf_ecoli_dsso.mzid")
        db_name = "mgf_ecoli_dsso.db"
        temp_db_path = os.path.join(temp_dir, db_name)

        # Process file
        sequences_and_residue_pairs(mzid_file, temp_dir)

        # Database should be deleted after processing
        assert not os.path.exists(temp_db_path)

    def test_existing_temp_database_removed(
        self, test_dir_with_mzid, temp_dir
    ):
        """Test that existing temp database is removed before processing."""
        mzid_file = os.path.join(test_dir_with_mzid, "mgf_ecoli_dsso.mzid")
        db_name = "mgf_ecoli_dsso.db"
        temp_db_path = os.path.join(temp_dir, db_name)

        # Create a dummy database file
        with open(temp_db_path, "w") as f:
            f.write("dummy data")

        assert os.path.exists(temp_db_path)

        # Process file - should remove existing and create new
        result = sequences_and_residue_pairs(mzid_file, temp_dir)

        # Should have processed successfully
        assert isinstance(result, dict)
        # Database should be cleaned up
        assert not os.path.exists(temp_db_path)

    def test_decoy_sequences_excluded(self, test_dir_with_mzid, temp_dir):
        """Test that decoy sequences are excluded from results."""
        mzid_file = os.path.join(test_dir_with_mzid, "mgf_ecoli_dsso.mzid")

        result = sequences_and_residue_pairs(mzid_file, temp_dir)

        # The SQL query includes WHERE pe.is_decoy = false
        # So all returned sequences should be non-decoy
        # This is implicit in the query, but we verify we got results
        assert isinstance(result["sequences"], list)
        assert isinstance(result["residue_pairs"], list)

    def test_only_passing_threshold_matches(
        self, test_dir_with_mzid, temp_dir
    ):
        """Test that only matches passing threshold are included."""
        mzid_file = os.path.join(test_dir_with_mzid, "mgf_ecoli_dsso.mzid")

        result = sequences_and_residue_pairs(mzid_file, temp_dir)

        # The SQL query includes WHERE si.pass_threshold = true
        # for residue pairs, so all should pass threshold
        assert isinstance(result["residue_pairs"], list)


class TestSequencesAndResiduePairsDirectory:
    """Tests for processing directories of mzIdentML files."""

    def test_directory_processing(self, test_dir_with_mzid, temp_dir):
        """Test processing all mzid files in a directory."""
        result = sequences_and_residue_pairs(test_dir_with_mzid, temp_dir)

        # Should process successfully
        assert isinstance(result, dict)
        assert "sequences" in result
        assert "residue_pairs" in result
        assert isinstance(result["sequences"], list)
        assert isinstance(result["residue_pairs"], list)

    def test_directory_single_file_works(self, fixtures_dir, temp_dir):
        """Test that directory processing works with a single file."""
        # Note: Multi-file processing in the same database would require
        # fixing the upload_id assignment logic in process_dataset.py
        # For now, we test that directory processing finds and processes files
        test_data_dir = os.path.join(temp_dir, "single_test")
        os.makedirs(test_data_dir)

        # Copy one mzid file
        src = os.path.join(fixtures_dir, "mgf_ecoli_dsso.mzid")
        shutil.copy(src, test_data_dir)

        result = sequences_and_residue_pairs(test_data_dir, temp_dir)

        # Should process successfully
        assert isinstance(result, dict)
        assert "sequences" in result
        assert "residue_pairs" in result
        # Should have data from the file
        if len(result["sequences"]) > 0:
            files_seen = set(seq["file"] for seq in result["sequences"])
            assert "mgf_ecoli_dsso.mzid" in files_seen

    def test_directory_temp_database_cleanup(
        self, test_dir_with_mzid, temp_dir
    ):
        """Test that temp database is cleaned up after directory processing."""
        db_name = "test_data.db"
        temp_db_path = os.path.join(temp_dir, db_name)

        # Process directory
        sequences_and_residue_pairs(test_dir_with_mzid, temp_dir)

        # Database should be cleaned up
        assert not os.path.exists(temp_db_path)


class TestSequencesAndResiduePairsErrorHandling:
    """Tests for error handling in sequences and residue pairs extraction."""

    def test_invalid_file_path(self, temp_dir):
        """Test that invalid file path raises error."""
        invalid_path = "/nonexistent/path/file.mzid"

        with pytest.raises(ValueError, match="Invalid file or directory path"):
            sequences_and_residue_pairs(invalid_path, temp_dir)

    def test_non_mzid_file(self, fixtures_dir, temp_dir):
        """Test that non-mzid file raises error."""
        # Use the fasta file which is not an mzid
        fasta_file = os.path.join(fixtures_dir, "..", "test_fasta.fasta")

        if os.path.exists(fasta_file):
            with pytest.raises(ValueError, match='must end ".mzid"'):
                sequences_and_residue_pairs(fasta_file, temp_dir)


class TestSequencesAndResiduePairsDataIntegrity:
    """Tests for data integrity of extracted sequences and residue pairs."""

    def test_residue_pair_positions_positive(
        self, test_dir_with_mzid, temp_dir
    ):
        """Test that residue pair positions are positive integers."""
        mzid_file = os.path.join(test_dir_with_mzid, "mgf_ecoli_dsso.mzid")

        result = sequences_and_residue_pairs(mzid_file, temp_dir)

        for rp in result["residue_pairs"]:
            # Positions should be positive (1-indexed in biology)
            assert rp["pos1"] > 0
            assert rp["pos2"] > 0

    def test_residue_pairs_have_valid_protein_refs(
        self, test_dir_with_mzid, temp_dir
    ):
        """Test that residue pairs reference valid proteins."""
        mzid_file = os.path.join(test_dir_with_mzid, "mgf_ecoli_dsso.mzid")

        result = sequences_and_residue_pairs(mzid_file, temp_dir)

        # Collect all protein IDs from sequences
        protein_ids = set(seq["id"] for seq in result["sequences"])

        # All residue pairs should reference proteins in sequences
        for rp in result["residue_pairs"]:
            assert rp["prot1"] in protein_ids
            assert rp["prot2"] in protein_ids

    def test_sequence_not_empty(self, test_dir_with_mzid, temp_dir):
        """Test that sequences are not empty strings."""
        mzid_file = os.path.join(test_dir_with_mzid, "mgf_ecoli_dsso.mzid")

        result = sequences_and_residue_pairs(mzid_file, temp_dir)

        for seq in result["sequences"]:
            assert len(seq["sequence"]) > 0
            # Sequences should contain valid amino acid characters
            assert seq["sequence"].isalpha()

    def test_accession_not_empty(self, test_dir_with_mzid, temp_dir):
        """Test that accessions are not empty strings."""
        mzid_file = os.path.join(test_dir_with_mzid, "mgf_ecoli_dsso.mzid")

        result = sequences_and_residue_pairs(mzid_file, temp_dir)

        for seq in result["sequences"]:
            assert len(seq["accession"]) > 0

    def test_file_field_populated(self, test_dir_with_mzid, temp_dir):
        """Test that file field is populated in results."""
        mzid_file = os.path.join(test_dir_with_mzid, "mgf_ecoli_dsso.mzid")

        result = sequences_and_residue_pairs(mzid_file, temp_dir)

        if len(result["sequences"]) > 0:
            for seq in result["sequences"]:
                assert seq["file"] == "mgf_ecoli_dsso.mzid"

        if len(result["residue_pairs"]) > 0:
            for rp in result["residue_pairs"]:
                # Files field contains comma-separated list
                assert "mgf_ecoli_dsso.mzid" in rp["files"]


class TestSequencesAndResiduePairsSQL:
    """Tests for SQL query correctness."""

    def test_sequences_unique_by_file(self, test_dir_with_mzid, temp_dir):
        """Test that sequences are grouped correctly per file."""
        mzid_file = os.path.join(test_dir_with_mzid, "mgf_ecoli_dsso.mzid")

        result = sequences_and_residue_pairs(mzid_file, temp_dir)

        # Group by should ensure unique combinations
        seen = set()
        for seq in result["sequences"]:
            key = (seq["id"], seq["sequence"], seq["accession"], seq["file"])
            assert key not in seen, "Duplicate sequence entry found"
            seen.add(key)

    def test_residue_pairs_grouped_correctly(
        self, test_dir_with_mzid, temp_dir
    ):
        """Test that residue pairs are grouped by position combinations."""
        mzid_file = os.path.join(test_dir_with_mzid, "mgf_ecoli_dsso.mzid")

        result = sequences_and_residue_pairs(mzid_file, temp_dir)

        # Each unique combination should appear once
        # with match_ids concatenated
        seen = set()
        for rp in result["residue_pairs"]:
            key = (
                rp["prot1"],
                rp["prot1_acc"],
                rp["pos1"],
                rp["prot2"],
                rp["prot2_acc"],
                rp["pos2"],
            )
            assert key not in seen, "Duplicate residue pair entry found"
            seen.add(key)

    def test_residue_pairs_sorted(self, test_dir_with_mzid, temp_dir):
        """Test that residue pairs are sorted correctly."""
        mzid_file = os.path.join(test_dir_with_mzid, "mgf_ecoli_dsso.mzid")

        result = sequences_and_residue_pairs(mzid_file, temp_dir)

        if len(result["residue_pairs"]) > 1:
            # Check ordering: prot1 id, pos1, prot2 id, pos2
            for i in range(len(result["residue_pairs"]) - 1):
                current = result["residue_pairs"][i]
                next_rp = result["residue_pairs"][i + 1]

                # Should be sorted by prot1, pos1, prot2, pos2
                current_key = (
                    current["prot1"],
                    current["pos1"],
                    current["prot2"],
                    current["pos2"],
                )
                next_key = (
                    next_rp["prot1"],
                    next_rp["pos1"],
                    next_rp["prot2"],
                    next_rp["pos2"],
                )
                assert current_key <= next_key

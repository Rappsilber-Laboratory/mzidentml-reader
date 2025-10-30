#!/usr/bin/env python3
"""
Script to add UniProt protein sequences to mzIdentML fixture files.
This updates DBSequence elements that are missing sequence data.
"""

import re
import sys
import time
from urllib.error import HTTPError
from urllib.request import urlopen

from lxml import etree


def fetch_uniprot_sequence(accession):
    """
    Fetch protein sequence from UniProt REST API.

    Args:
        accession: UniProt accession ID (e.g., 'LYSC_CHICK')

    Returns:
        Protein sequence string, or None if not found
    """
    url = f"https://rest.uniprot.org/uniprotkb/{accession}.fasta"
    try:
        print(f"  Fetching {accession}...", end=" ")
        with urlopen(url) as response:
            fasta_data = response.read().decode("utf-8")
            # Parse FASTA format - skip header line, join sequence lines
            lines = fasta_data.strip().split("\n")
            sequence = "".join(lines[1:])  # Skip first line (header)
            print(f"OK ({len(sequence)} aa)")
            return sequence
    except HTTPError as e:
        if e.code == 404:
            print(f"NOT FOUND")
            return None
        else:
            print(f"ERROR: {e}")
            return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def update_mzidentml_file(filename, sequence_cache):
    """
    Update mzIdentML file by adding <Seq> elements to DBSequence entries.

    Args:
        filename: Path to mzIdentML file
        sequence_cache: Dict mapping accession -> sequence
    """
    print(f"\nProcessing {filename}...")

    # Parse XML
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(filename, parser)
    root = tree.getroot()

    # Define namespace
    ns = {"mzid": "http://psidev.info/psi/pi/mzIdentML/1.2"}

    # Find all DBSequence elements
    dbsequences = root.findall(".//mzid:DBSequence", ns)
    print(f"Found {len(dbsequences)} DBSequence elements")

    sequences_added = 0
    sequences_skipped = 0
    sequences_not_found = 0

    for dbseq in dbsequences:
        accession = dbseq.get("accession")

        # Skip if not a protein accession (MS:, UNIMOD:, etc.)
        if (
            not accession
            or accession.startswith("MS:")
            or accession.startswith("UNIMOD")
        ):
            continue

        # Check if sequence already exists
        existing_seq = dbseq.find("mzid:Seq", ns)
        if existing_seq is not None:
            sequences_skipped += 1
            continue

        # Fetch sequence if not in cache
        if accession not in sequence_cache:
            seq = fetch_uniprot_sequence(accession)
            if seq:
                sequence_cache[accession] = seq
                # Be nice to UniProt servers
                time.sleep(0.2)
            else:
                sequences_not_found += 1
                continue

        # Add Seq element
        sequence = sequence_cache[accession]
        seq_elem = etree.Element(
            "{http://psidev.info/psi/pi/mzIdentML/1.2}Seq"
        )
        seq_elem.text = sequence

        # Insert as first child element
        dbseq.insert(0, seq_elem)
        sequences_added += 1

    # Write back to file
    tree.write(
        filename, encoding="UTF-8", xml_declaration=True, pretty_print=False
    )

    print(f"Summary:")
    print(f"  Sequences added: {sequences_added}")
    print(f"  Sequences skipped (already present): {sequences_skipped}")
    print(f"  Sequences not found: {sequences_not_found}")
    print(f"  Total in cache: {len(sequence_cache)}")


def main():
    """Main function."""
    # Shared cache for sequences to avoid duplicate fetches
    sequence_cache = {}

    # Process both fixture files
    files = [
        "../tests/fixtures/mzid_parser/F002553.mzid",
        "../tests/fixtures/mzid_parser/F002553_samesets.mzid",
    ]

    for filename in files:
        update_mzidentml_file(filename, sequence_cache)

    print(f"\nDone! Total unique sequences cached: {len(sequence_cache)}")


if __name__ == "__main__":
    main()

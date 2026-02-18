"""schema_validate.py - Validate an mzIdentML file against XSD schema using xmllint."""

import os
import subprocess
import xml.etree.ElementTree as ET
from typing import List, Tuple

# Path to schema files relative to this script
SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..", "schema")

# Supported schema files
SUPPORTED_SCHEMAS = [
    "mzIdentML1.0.0.xsd",
    "mzIdentML1.1.0.xsd",
    "mzIdentML1.1.1.xsd",
    "mzIdentML1.2.0.xsd",
    "mzIdentML1.3.0.xsd",
]

VALIDATION_TIMEOUT = 30 * 60 # 30 minute timeout

def _extract_schema_version(schema_fname: str) -> str | None:
    """Extract version string from schema filename (e.g., '1.2.0' from 'mzIdentML1.2.0.xsd')."""
    if schema_fname.startswith("mzIdentML") and schema_fname.endswith(".xsd"):
        return schema_fname[9:-4]  # Remove 'mzIdentML' prefix and '.xsd' suffix
    return None


def _get_schema_fname(xml_file: str) -> Tuple[str | None, str | None, List[str]]:
    """Extract the schema filename from the root element's attributes.

    Uses iterparse to read only the root element without loading the full file.

    Returns:
        Tuple of (schema_fname, schema_version, messages)
    """
    messages = []
    schema_location = None

    try:
        for event, elem in ET.iterparse(xml_file, events=("start",)):
            # First 'start' event is the root element
            schema_location = elem.attrib.get(
                "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation"
            )
            if not schema_location:
                schema_location = elem.attrib.get(
                    "{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation"
                )
            break
    except ET.ParseError as e:
        messages.append(f"Failed to parse root element: {e}")
        return None, None, messages

    if not schema_location:
        messages.append("No schema location found in the XML document.")
        return None, None, messages

    schema_parts = schema_location.split()
    if len(schema_parts) % 2 != 0:
        messages.append("Invalid schema location format.")
        return None, None, messages

    schema_url = schema_parts[1] if len(schema_parts) == 2 else schema_parts[-1]
    schema_fname = schema_url.split("/")[-1]
    return schema_fname, _extract_schema_version(schema_fname), messages


def schema_validate(xml_file: str) -> bool:
    """Validate an mzIdentML file against its declared schema.

    Args:
        xml_file: Path to the mzIdentML file

    Returns:
        True if the XML is valid, False otherwise
    """
    success, schema_version, messages = schema_validate_with_messages(xml_file)
    for msg in messages:
        print(msg)
    return success


def schema_validate_with_messages(xml_file: str, timeout: int = VALIDATION_TIMEOUT) -> Tuple[bool, str | None, List[str]]:
    """Validate an mzIdentML file and return validation messages.

    Uses xmllint with --stream to avoid high memory usage.

    Args:
        xml_file: Path to the mzIdentML file
        timeout: Maximum seconds to wait for validation (default 7200)

    Returns:
        Tuple of (success, schema_version, list of error/info messages)
    """
    schema_fname, schema_version, messages = _get_schema_fname(xml_file)
    if schema_fname is None:
        return False, schema_version, messages

    if schema_fname not in SUPPORTED_SCHEMAS:
        messages.append(f"Unsupported schema: {schema_fname}")
        return False, schema_version, messages

    schema_path = os.path.join(SCHEMA_DIR, schema_fname)
    if not os.path.exists(schema_path):
        messages.append(f"Schema file not found: {schema_path}")
        return False, schema_version, messages

    # Check well-formedness first (xmllint gives poor schema errors for malformed XML)
    try:
        result = subprocess.run(
            ["xmllint", "--stream", "--noout", xml_file],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        messages.append("xmllint not found. Install libxml2-utils.")
        return False, schema_version, messages
    except subprocess.TimeoutExpired:
        messages.append(f"Well-formedness check timed out after {timeout}s")
        return False, schema_version, messages

    if result.returncode != 0:
        stderr_lines = result.stderr.strip().splitlines()
        messages.append("XML is not well-formed. First 20 errors:")
        for line in stderr_lines[:20]:
            messages.append(line)
        return False, schema_version, messages

    try:
        result = subprocess.run(
            ["xmllint", "--schema", schema_path, "--stream", "--noout", xml_file],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        messages.append("xmllint not found. Install libxml2-utils.")
        return False, schema_version, messages
    except subprocess.TimeoutExpired:
        messages.append(f"Validation timed out after {timeout}s")
        return True, schema_version, messages

    if result.returncode == 0:
        return True, schema_version, messages

    # xmllint writes errors to stderr
    stderr_lines = result.stderr.strip().splitlines()
    messages.append("XML is invalid. First 20 errors:")
    for line in stderr_lines[:20]:
        messages.append(line)
    return False, schema_version, messages


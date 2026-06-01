"""schema_validate.py - Validate an mzIdentML file against XSD schema using xmllint."""

import os
import re
import subprocess
import xml.etree.ElementTree as ET
from typing import List, Tuple

# Matches an X.Y.Z version anywhere in a schema filename, allowing for
# pre-release suffixes like "1.2.0-candidate" — we resolve those to the
# canonical "1.2.0" schema.
_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+)")

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

VALIDATION_TIMEOUT = 10 * 60 # 10 minute timeout

def _extract_schema_version(schema_fname: str) -> str | None:
    """Extract an X.Y.Z version from a schema filename.

    Matches the first X.Y.Z occurrence, so pre-release names like
    'mzIdentML1.2.0-candidate.xsd' resolve to '1.2.0'.
    """
    match = _VERSION_RE.search(schema_fname)
    return match.group(1) if match else None


# Highest supported schema, used as the fallback when a file's declared
# version/schemaLocation cannot be resolved to a bundled schema.
_HIGHEST_SCHEMA = max(
    SUPPORTED_SCHEMAS,
    key=lambda s: tuple(int(p) for p in _extract_schema_version(s).split(".")),
)


def _resolve_supported(raw: str) -> Tuple[str | None, str | None]:
    """Resolve a raw version/filename string to a bundled schema.

    Extracts an X.Y.Z version, builds the canonical 'mzIdentML{X.Y.Z}.xsd' name,
    and returns (fname, version) if it is a supported schema, else (None, None).
    """
    version = _extract_schema_version(raw)
    if version is None:
        return None, None
    fname = f"mzIdentML{version}.xsd"
    if fname in SUPPORTED_SCHEMAS:
        return fname, version
    return None, None


def _get_schema_fname(xml_file: str) -> Tuple[str | None, str | None, List[str]]:
    """Determine which bundled schema to validate the file against.

    Uses iterparse to read only the root element without loading the full file.
    Resolution order: the required 'version' attribute first, then
    'schemaLocation', and finally a default to the highest supported schema if
    neither resolves to a bundled schema.

    Returns:
        Tuple of (schema_fname, schema_version, messages). schema_fname is None
        only when the root element cannot be parsed.
    """
    messages = []
    schema_location = None
    version = None

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
            version = elem.attrib.get("version")
            break
    except ET.ParseError as e:
        messages.append(f"Failed to parse root element: {e}")
        return None, None, messages

    # 1. The version attribute is required by the mzIdentML spec — prefer it.
    if version:
        fname, resolved_version = _resolve_supported(version)
        if fname:
            messages.append(
                f"Using schema {fname} (from version attribute '{version}')."
            )
            return fname, resolved_version, messages

    # 2. Fall back to schemaLocation.
    if schema_location:
        schema_parts = schema_location.split()
        if len(schema_parts) % 2 != 0:
            messages.append("Invalid schema location format.")
        else:
            raw_fname = schema_parts[-1].split("/")[-1]
            fname, resolved_version = _resolve_supported(raw_fname)
            if fname:
                messages.append(
                    f"Using schema {fname} (resolved from schemaLocation '{raw_fname}')."
                )
                return fname, resolved_version, messages

    # 3. Nothing resolved — default to the highest supported schema.
    resolved_version = _extract_schema_version(_HIGHEST_SCHEMA)
    messages.append(
        f"Could not resolve a supported schema (version={version!r}, "
        f"schemaLocation={schema_location!r}); defaulting to highest "
        f"supported schema {_HIGHEST_SCHEMA}."
    )
    return _HIGHEST_SCHEMA, resolved_version, messages


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


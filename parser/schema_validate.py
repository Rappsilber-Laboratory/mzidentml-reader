"""schema_validate.py - Validate an mzIdentML file against 1.2.0 or 1.3.0 schema."""

from importlib.resources import as_file, files
from multiprocessing import Pool
from typing import List, Tuple

from lxml import etree


def schema_validate(xml_file: str) -> bool:
    """Validate an mzIdentML file against 1.2.0 or 1.3.0 schema.

    Runs validation in a subprocess to ensure memory is fully released
    after validation completes (lxml/libxml2 holds memory otherwise).

    Args:
        xml_file: Path to the mzIdentML file

    Returns:
        True if the XML is valid, False otherwise
    """
    with Pool(1) as pool:
        success, messages = pool.apply(_schema_validate_impl, (xml_file,))

    for msg in messages:
        print(msg)

    return success


def _schema_validate_impl(xml_file: str) -> Tuple[bool, List[str]]:
    """Internal implementation of schema validation (runs in subprocess).

    Returns:
        Tuple of (success, list of messages to print)
    """
    messages = []
    # Parse the XML file
    with open(xml_file, "r") as xml:
        xml_doc = etree.parse(xml)

    # Extract schema location from the XML (xsi:schemaLocation or xsi:noNamespaceSchemaLocation)
    root = xml_doc.getroot()
    schema_location = root.attrib.get(
        "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation"
    )

    if not schema_location:
        schema_location = root.attrib.get(
            "{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation"
        )

    if not schema_location:
        messages.append("No schema location found in the XML document.")
        return False, messages

    # The schemaLocation attribute may contain multiple namespaces and schema locations.
    # Typically, it's formatted as "namespace schemaLocation" pairs.
    schema_parts = schema_location.split()
    if len(schema_parts) % 2 != 0:
        messages.append("Invalid schema location format.")
        return False, messages

    # Assuming a single namespace-schema pair for simplicity
    schema_url = (
        schema_parts[1] if len(schema_parts) == 2 else schema_parts[-1]
    )

    # just take the file name from the url
    schema_fname = schema_url.split("/")[-1]
    # if not 1.2.0 or 1.3.0
    if schema_fname not in ["mzIdentML1.2.0.xsd", "mzIdentML1.3.0.xsd"]:
        messages.append(
            f"Sorry, we're only supporting 1.2.0 and 1.3.0 (the ones that "
            f"contain crosslinks). Rejected schema file: {schema_fname}"
        )
        return False, messages

    try:
        schema_path = files("schema").joinpath(schema_fname)
        with as_file(schema_path) as schema_file:
            with open(schema_file, "r") as schema_file_stream:
                schema_root = etree.XML(schema_file_stream.read())
            schema = etree.XMLSchema(schema_root)

            if schema.validate(xml_doc):
                return True, messages
            else:
                messages.append("XML is invalid. First 20 errors:")
                for error in schema.error_log[:20]:
                    messages.append(
                        f"Error: {error.message}, Line: {error.line}"
                    )
                return False, messages

    except FileNotFoundError:
        messages.append("Schema file not found.")
        return False, messages

"""schema_validate.py - Validate an mzIdentML file against 1.2.0 or 1.3.0 schema."""

from importlib.resources import as_file, files

from lxml import etree


def schema_validate(xml_file: str) -> bool:
    """Validate an mzIdentML file against 1.2.0 or 1.3.0 schema.

    Args:
        xml_file: Path to the mzIdentML file

    Returns:
        True if the XML is valid, False otherwise
    """
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
        print("No schema location found in the XML document.")
        return False

    # The schemaLocation attribute may contain multiple namespaces and schema locations.
    # Typically, it's formatted as "namespace schemaLocation" pairs.
    schema_parts = schema_location.split()
    if len(schema_parts) % 2 != 0:
        print("Invalid schema location format.")
        return False

    # Assuming a single namespace-schema pair for simplicity
    schema_url = (
        schema_parts[1] if len(schema_parts) == 2 else schema_parts[-1]
    )

    # just take the file name from the url
    schema_fname = schema_url.split("/")[-1]
    # if not 1.2.0 or 1.3.0
    if schema_fname not in ["mzIdentML1.2.0.xsd", "mzIdentML1.3.0.xsd"]:
        print(
            f"Sorry, we're only supporting 1.2.0 and 1.3.0 (the ones that contain crosslinks). Rejected schema file: {schema_fname}"
        )
        return False

    try:
        schema_path = files("schema").joinpath(schema_fname)
        with as_file(schema_path) as schema_file:
            with open(schema_file, "r") as schema_file_stream:
                schema_root = etree.XML(schema_file_stream.read())
            schema = etree.XMLSchema(schema_root)

            if schema.validate(xml_doc):
                return True
            else:
                print("XML is invalid. First 20 errors:")
                for error in schema.error_log[:20]:
                    print(f"Error: {error.message}, Line: {error.line}")
                return False

    except FileNotFoundError:
        print("Schema file not found.")
        return False

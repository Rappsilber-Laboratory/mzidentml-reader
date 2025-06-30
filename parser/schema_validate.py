"""schema_validate.py - Validate an mzIdentML file against 1.2.0 or 1.3.0 schema."""
import importlib

from lxml import etree

def schema_validate(xml_file):
    """
    Validate an mzIdentML file against 1.2.0 or 1.3.0 schema.
    :param xml_file: Path to the mzIdentML file.
    :return: True if the XML is valid, False otherwise.
    """
    # Parse the XML file
    with open(xml_file, 'r') as xml:
        xml_doc = etree.parse(xml)

    # Extract schema location from the XML (xsi:schemaLocation or xsi:noNamespaceSchemaLocation)
    root = xml_doc.getroot()
    schema_location = root.attrib.get('{http://www.w3.org/2001/XMLSchema-instance}schemaLocation')

    if not schema_location:
        schema_location = root.attrib.get('{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation')

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
    schema_url = schema_parts[1] if len(schema_parts) == 2 else schema_parts[-1]

    # just take the file name from the url
    schema_fname = schema_url.split('/')[-1]
    # if not 1.2.0 or 1.3.0
    if schema_fname not in ['mzIdentML1.2.0.xsd', 'mzIdentML1.3.0.xsd']:
        print(f"Sorry, we're only supporting 1.2.0 and 1.3.0 (the ones that contain crosslinks). Rejected schema file: {schema_fname}")
        return False

    try:
        # Access `logging.ini` as a resource inside the package
        with importlib.resources.path('schema', schema_fname) as schema_file:
            # current_directory = os.getcwd()
            # # print(f"Current working directory: {current_directory}")
            # # read from scehma directory
            # schema_file = os.path.join(current_directory, '..', 'schema', schema_fname)
            # # Parse the XSD file
            with open(schema_file, 'r') as schema_file_stream:
                schema_root = etree.XML(schema_file_stream.read())
            schema = etree.XMLSchema(schema_root)

            # Validate XML against the schema
            if schema.validate(xml_doc):
                # print("XML is valid.")
                return True
            else:
                # Print out any validation errors
                print("XML is invalid. First 20 errors:")
                # get first 20 errors from schema.error_log
                for error in schema.error_log[:20]:
                    print(f"Error: {error.message}, Line: {error.line}")
                return False

    except FileNotFoundError:
        print("Schema file not found.")




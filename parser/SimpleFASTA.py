"""SimpleFASTA.py - Parse a FASTA file and return a dictionary of the sequences."""

import re

#  why aren't we using pyteomics? todo? probably we haven't look at yet coz its only used by cvs parsers not mzid


# noinspection PyUnusedLocal
def get_db_sequence_dict(fasta_file_list):
    """
    Parse a FASTA file and return a dictionary of the sequences.
    :param fasta_file_list:
    :return: dict
    """
    db_sequence_dict = {}
    identifier = None
    sequence = ""
    description = None
    for fasta_file in fasta_file_list:
        for line in open(fasta_file).read().splitlines():
            # semi-colons indicate comments, ignore them
            if not line.startswith(";"):
                if line.startswith(">"):
                    if identifier is not None:
                        add_entry(
                            identifier, sequence, description, db_sequence_dict
                        )
                        identifier = None
                        sequence = ""
                        description = None

                    # get new identifier
                    identifier = line
                    if " " not in line:
                        identifier = line[1:].rstrip()
                    else:
                        i_first_space = line.index(" ")
                        identifier = line[1:i_first_space].rstrip()
                        description = line[i_first_space:].rstrip()
                else:
                    sequence += line.rstrip()

    # add last entry
    if identifier is not None:
        add_entry(identifier, sequence, description, db_sequence_dict)

    return db_sequence_dict


def add_entry(identifier, sequence, description, seq_dict):
    """
    Add an entry to the sequence dictionary.
    :param identifier:
    :param sequence:
    :param description:
    :param seq_dict:
    :return: None
    """
    m = re.search(r"..\|(.*)\|(.*)\s?", identifier)
    # id = identifier
    accession = identifier
    name = identifier
    if m:
        accession = m.groups()[0]
        name = m.groups()[1]

    data = [accession, name, description, sequence]
    seq_dict[identifier] = data
    seq_dict[accession] = data

"""Writer.py - Abstract class for writing results to a database."""

from abc import ABC, abstractmethod


# Strategy interface
class Writer(ABC):
    """
    Interface for writing results to a database.
    """

    def __init__(self, upload_id=None, pxid=None):
        self.pxid = pxid
        self.upload_id = upload_id

    @abstractmethod
    def write_data(self, table, data):
        """
        Insert data into table.
        :param table:
        :param data:
        """
        pass

    @abstractmethod
    def write_new_upload(self, table, data):
        """
        Insert data into upload table and, if postgres, return the id of the new row.
        :param table:
        :param data:
        """
        pass

    @abstractmethod
    def write_mzid_info(
        self,
        analysis_software_list,
        spectra_formats,
        provider,
        audits,
        samples,
        bib,
        upload_id,
    ):
        """
        Update the mzid_info table with the given data.
        :param analysis_software_list:
        :param spectra_formats:
        :param provider:
        :param audits:
        :param samples:
        :param bib:
        :param upload_id:
        """
        pass

    @abstractmethod
    def fill_in_missing_scores(self):
        """
        Legacy xiSPEC thing, can be ignored,
        just leaving in rather than creating a backwards compatibility issue for xiSPEC
        todo - probably remove
        """
        pass

"""Writer.py - Abstract class for writing results to a database."""

from abc import ABC, abstractmethod
from typing import Any


# Strategy interface
class Writer(ABC):
    """Interface for writing results to a database."""

    def __init__(
        self, upload_id: int | None = None, pxid: str | None = None
    ) -> None:
        self.pxid = pxid
        self.upload_id = upload_id

    @abstractmethod
    def write_data(
        self, table: str, data: list[dict[str, Any]] | dict[str, Any]
    ) -> None:
        """Insert data into table.

        Args:
            table: Table name
            data: Data to insert
        """
        pass

    @abstractmethod
    def write_new_upload(self, table: str, data: dict[str, Any]) -> int | None:
        """Insert data into upload table and, if postgres, return the id of the new row.

        Args:
            table: Table name
            data: Data to insert

        Returns:
            ID of the newly created row, or None
        """
        pass

    @abstractmethod
    def write_mzid_info(
        self,
        analysis_software_list: dict[str, Any],
        spectra_formats: list[Any],
        provider: dict[str, Any],
        audits: dict[str, Any],
        samples: dict[str, Any] | list[Any],
        bib: list[Any],
        upload_id: int,
    ) -> None:
        """Update the mzid_info table with the given data.

        Args:
            analysis_software_list: List of analysis software used
            spectra_formats: List of spectra format information
            provider: Provider information
            audits: Audit collection information
            samples: Analysis sample collection information
            bib: Bibliographic references
            upload_id: Upload identifier
        """
        pass

    @abstractmethod
    def fill_in_missing_scores(self) -> None:
        """Legacy xiSPEC thing, can be ignored.

        Just leaving in rather than creating a backwards compatibility issue
        for xiSPEC. todo - probably remove
        """
        pass

    @abstractmethod
    def write_other_info(
        self, contains_crosslinks: bool, warnings: list[str], upload_id: int
    ) -> None:
        """Write remaining information into Upload table.

        Args:
            contains_crosslinks: Whether the upload contains crosslink data
            warnings: List of warning messages
            upload_id: Upload identifier
        """
        pass

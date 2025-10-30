"""DatabaseWriter class for writing results to a postgresql relational database."""

from parser.database.create_db_schema import create_schema
from parser.Writer import Writer
from typing import Any

from sqlalchemy import MetaData, Table, create_engine
from sqlalchemy_utils import database_exists


class DatabaseWriter(Writer):
    """Class for writing results to a relational database."""

    def __init__(
        self,
        connection_str: str,
        upload_id: int | None = None,
        pxid: str | None = None,
    ) -> None:
        """Initialises the database connection and the writer in general.

        Args:
            connection_str: Database connection string
            upload_id: Upload identifier
            pxid: ProteomeXchange identifier
        """
        # Connection setup.
        # The 'engine' in SQLAlchemy is a Factory and connection pool to the database.
        # It has lazy initialisation.
        super().__init__(upload_id, pxid)
        self.engine = create_engine(connection_str)
        self.meta = MetaData()
        self.pxid = pxid
        self.upload_id = upload_id
        # Create table schema if necessary (SQLite) - not working for postgresql - why?
        if not database_exists(self.engine.url):
            create_schema(self.engine.url)

    def write_data(
        self, table: str, data: list[dict[str, Any]] | dict[str, Any]
    ) -> None:
        """Insert data into table.

        Args:
            table: Table name
            data: Data to insert (dict or list of dicts)
        """
        # print(data)
        if isinstance(data, dict):
            data = [data]

        keys = list(set([k for r in data for k in r.keys()]))
        for r in data:
            for k in keys:
                if k not in r:
                    r[k] = None
        table = Table(table, self.meta, autoload_with=self.engine)
        with self.engine.connect() as conn:
            statement = table.insert().values(data)
            conn.execute(statement)
            conn.commit()
            conn.close()

    def write_new_upload(self, table: str, data: dict[str, Any]) -> int:
        """Insert data into upload table and return the id of the new row.

        Args:
            table: Table name
            data: Data to insert

        Returns:
            ID of the newly created row
        """
        table = Table(table, self.meta, autoload_with=self.engine, quote=False)
        with self.engine.connect() as conn:
            statement = (
                table.insert().values(data).returning(table.columns[0])
            )  # RETURNING id AS upload_id
            result = conn.execute(statement)
            conn.commit()
            conn.close()
        return result.fetchall()[0][0]

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
        """Update Upload row with mzid info.

        Args:
            analysis_software_list: List of analysis software used
            spectra_formats: List of spectra format information
            provider: Provider information
            audits: Audit collection information
            samples: Analysis sample collection information
            bib: Bibliographic references
            upload_id: Upload identifier
        """
        upload = Table(
            "upload", self.meta, autoload_with=self.engine, quote=False
        )
        # noinspection PyTypeChecker
        stmt = (
            upload.update()
            .where(upload.c.id == str(upload_id))
            .values(
                analysis_software_list=analysis_software_list,
                spectra_formats=spectra_formats,
                provider=provider,
                audit_collection=audits,
                analysis_sample_collection=samples,
                bib=bib,
            )
        )
        with self.engine.connect() as conn:
            conn.execute(stmt)
            conn.commit()

    def write_other_info(
        self,
        contains_crosslinks: bool,
        upload_warnings: list[str],
        upload_id: int,
    ) -> None:
        """Update Upload row with remaining info.

        ToDo: have this explicitly or create update func?

        Args:
            contains_crosslinks: Whether the upload contains crosslink data
            upload_warnings: List of warning messages
            upload_id: Upload identifier
        """
        upload = Table(
            "upload", self.meta, autoload_with=self.engine, quote=False
        )
        with self.engine.connect() as conn:
            # noinspection PyTypeChecker
            stmt = (
                upload.update()
                .where(upload.c.id == str(upload_id))
                .values(
                    contains_crosslinks=contains_crosslinks,
                    upload_warnings=upload_warnings,
                )
            )
            conn.execute(stmt)
            conn.commit()

    def fill_in_missing_scores(self) -> None:
        """ToDo: this needs to be adapted to sqlalchemy from old SQLite version."""
        pass

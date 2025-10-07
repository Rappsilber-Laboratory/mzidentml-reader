"""
This file contains the AnalysisCollectionSpectrumIdentification class,
which is a SQLAlchemy model for the analysiscollectionspectrumidentification table in the database.
"""

from sqlalchemy import (
    JSON,
    Any,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class AnalysisCollectionSpectrumIdentification(Base):
    """
    This is the inputspectra.
    """

    __tablename__ = "analysiscollectionspectrumidentification"
    upload_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("upload.id"),
        index=True,
        primary_key=True,
        nullable=False,
    )
    # using spectrum_identification_list_ref as part of primary key not id - provides a sanity check on mzid file
    spectrum_identification_list_ref: Mapped[str] = mapped_column(
        Text, primary_key=True, nullable=False
    )
    spectrum_identification_protocol_ref: Mapped[str] = mapped_column(
        Text, primary_key=False, nullable=False
    )
    spectrum_identification_id: Mapped[str] = mapped_column(
        Text, primary_key=False, nullable=False
    )
    # # actvity date as time ?
    # activity_date:
    # # name ?
    # name:
    spectra_data_refs: Mapped[dict[str, Any]] = mapped_column(
        JSON, primary_key=False, nullable=True
    )
    search_database_refs: Mapped[dict[str, Any]] = mapped_column(
        JSON, primary_key=False, nullable=True
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["spectrum_identification_protocol_ref", "upload_id"],
            [
                "spectrumidentificationprotocol.sip_ref",
                "spectrumidentificationprotocol.upload_id",
            ],
        ),
    )

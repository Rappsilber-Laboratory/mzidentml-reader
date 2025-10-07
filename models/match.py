"""This file contains the Match class, which is a SQLAlchemy model for the match table in the database."""

from typing import Any, Optional

from sqlalchemy import (
    BOOLEAN,
    CHAR,
    FLOAT,
    JSON,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Match(Base):
    __tablename__ = "match"
    id: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    upload_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("upload.id"),
        index=True,
        primary_key=True,
        nullable=False,
    )
    spectrum_id: Mapped[str] = mapped_column(Text, nullable=True)
    spectra_data_id: Mapped[int] = mapped_column(
        Integer, nullable=True
    )  # nullable for csv data
    multiple_spectra_identification_id: Mapped[str] = mapped_column(
        Integer, nullable=True
    )
    multiple_spectra_identification_pc: Mapped[str] = mapped_column(
        CHAR, nullable=True
    )
    pep1_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    pep2_id: Mapped[int] = mapped_column(Integer, index=True, nullable=True)
    charge_state: Mapped[int] = mapped_column(Integer, nullable=True)
    pass_threshold: Mapped[bool] = mapped_column(BOOLEAN, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    scores: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    exp_mz: Mapped[float] = mapped_column(FLOAT, nullable=True)
    calc_mz: Mapped[float] = mapped_column(FLOAT, nullable=True)
    sip_id: Mapped[int] = mapped_column(
        Integer, nullable=True
    )  # null if from csv file
    __table_args__ = (
        ForeignKeyConstraint(
            ["sip_id", "upload_id"],
            [
                "spectrumidentificationprotocol.id",
                "spectrumidentificationprotocol.upload_id",
            ],
        ),
        ForeignKeyConstraint(
            [
                "upload_id",
                "pep1_id",
            ],
            ["modifiedpeptide.upload_id", "modifiedpeptide.id"],
        ),
        ForeignKeyConstraint(
            ["upload_id", "pep2_id"],
            [
                "modifiedpeptide.upload_id",
                "modifiedpeptide.id",
            ],
        ),
        # ForeignKeyConstraint(
        # ["spectrum_id", "spectra_data_id", "upload_id"],
        # ["spectrum.id", "spectrum.spectra_data_id", "spectrum.upload_id"],
        # ),
        Index("ix_match_id", "id"),
        # CREATE INDEX idx_match_pep1_id ON match (upload_id, pep1_id);
        # CREATE INDEX idx_match_pep2_id ON match (upload_id, pep2_id);
        Index("idx_match_pep1_id", "upload_id", "pep1_id"),
        Index("idx_match_pep2_id", "upload_id", "pep2_id"),
    )

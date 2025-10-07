"""
This file contains the PeptideEvidence class,
which is a SQLAlchemy model for the peptideevidence table in the database.
"""

from sqlalchemy import (
    BOOLEAN,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class PeptideEvidence(Base):
    __tablename__ = "peptideevidence"
    upload_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("upload.id"),
        index=True,
        primary_key=True,
        nullable=False,
    )
    peptide_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, nullable=False, index=True
    )
    dbsequence_id: Mapped[str] = mapped_column(
        Text, primary_key=True, nullable=False
    )
    pep_start: Mapped[int] = mapped_column(
        Integer, primary_key=True, nullable=False
    )
    is_decoy: Mapped[bool] = mapped_column(BOOLEAN, nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ("upload_id", "dbsequence_id"),
            ("dbsequence.upload_id", "dbsequence.id"),
        ),
        ForeignKeyConstraint(
            ("upload_id", "peptide_id"),
            ("modifiedpeptide.upload_id", "modifiedpeptide.id"),
        ),
        # add index on upload_id, peptide_id
        Index(
            "peptideevidence_upload_id_peptide_id_idx",
            "upload_id",
            "peptide_id",
        ),
    )

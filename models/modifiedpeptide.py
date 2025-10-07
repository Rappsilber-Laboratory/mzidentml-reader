"""
This file contains the ModifiedPeptide class,
which is a SQLAlchemy model for the modifiedpeptide table in the database.
"""

from typing import Any, Optional

from sqlalchemy import FLOAT, JSON, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ModifiedPeptide(Base):
    __tablename__ = "modifiedpeptide"
    upload_id: Mapped[str] = mapped_column(
        Integer,
        ForeignKey("upload.id"),
        index=True,
        primary_key=True,
        nullable=False,
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    base_sequence: Mapped[str] = mapped_column(Text, nullable=False)
    mod_accessions: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )
    mod_avg_mass_deltas: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    mod_monoiso_mass_deltas: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    # 1-based with 0 = n-terminal and len(pep)+1 = C-terminal
    mod_positions: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    # following columns are not in xi2 db, but come out of the mzid on the <Peptide>s
    link_site1: Mapped[int] = mapped_column(Integer, nullable=True)
    link_site2: Mapped[int] = mapped_column(
        Integer, nullable=True
    )  # only used for storing loop links
    crosslinker_modmass: Mapped[float] = mapped_column(FLOAT, nullable=True)
    crosslinker_pair_id: Mapped[str] = mapped_column(
        Text, nullable=True
    )  # yes, it's a string
    # CREATE INDEX ix_modifiedpeptide_id ON public.modifiedpeptide USING btree (id);
    # CREATE INDEX modifiedpeptide_upload_id__id_seq_idx ON public.modifiedpeptide (upload_id,id, base_sequence);
    # CREATE INDEX modifiedpeptide_upload_id_linksite_idx ON public.modifiedpeptide (upload_id, link_site1);
    __table_args__ = (
        Index("ix_modifiedpeptide_id", "id"),
        Index(
            "modifiedpeptide_upload_id__id_seq_idx",
            "upload_id",
            "id",
            "base_sequence",
        ),
        Index(
            "modifiedpeptide_upload_id_linksite_idx", "upload_id", "link_site1"
        ),
    )

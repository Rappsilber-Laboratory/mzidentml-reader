"""This file contains the Enzyme class, which is a SQLAlchemy model for the enzyme table in the database."""

from sqlalchemy import BOOLEAN, ForeignKey, ForeignKeyConstraint, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Enzyme(Base):
    __tablename__ = "enzyme"
    id: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    upload_id: Mapped[str] = mapped_column(
        Integer, ForeignKey("upload.id"), primary_key=True, nullable=False
    )
    protocol_id: Mapped[str] = mapped_column(
        Text, primary_key=True, nullable=False
    )
    c_term_gain: Mapped[str] = mapped_column(Text, nullable=True)
    min_distance: Mapped[int] = mapped_column(Integer, nullable=True)
    missed_cleavages: Mapped[int] = mapped_column(Integer, nullable=True)
    n_term_gain: Mapped[str] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=True)
    semi_specific: Mapped[bool] = mapped_column(BOOLEAN, nullable=True)
    site_regexp: Mapped[str] = mapped_column(Text, nullable=True)
    accession: Mapped[str] = mapped_column(Text, nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ("protocol_id", "upload_id"),
            (
                "spectrumidentificationprotocol.sip_ref",
                "spectrumidentificationprotocol.upload_id",
            ),
        ),
    )

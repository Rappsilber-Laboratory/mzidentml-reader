from typing import Any, Optional

from sqlalchemy import (
    BIGINT,
    BOOLEAN,
    FLOAT,
    JSON,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class SearchModification(Base):
    __tablename__ = "searchmodification"
    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, nullable=False)
    upload_id: Mapped[str] = mapped_column(
        Integer, ForeignKey("upload.id"), primary_key=True, nullable=False
    )
    protocol_id: Mapped[str] = mapped_column(
        Text, primary_key=True, nullable=False
    )
    mass: Mapped[float] = mapped_column(
        FLOAT, nullable=True
    )  # only nullable to accommodate errors in mzIdentML
    residues: Mapped[str] = mapped_column(Text, nullable=False)
    fixed_mod: Mapped[bool] = mapped_column(BOOLEAN, nullable=False)
    accessions: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=False
    )
    crosslinker_id: Mapped[str] = mapped_column(Text, nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ("protocol_id", "upload_id"),
            (
                "spectrumidentificationprotocol.sip_ref",
                "spectrumidentificationprotocol.upload_id",
            ),
        ),
    )

from sqlalchemy import (
    FLOAT,
    SMALLINT,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Spectrum(Base):
    __tablename__ = "spectrum"
    id: Mapped[str] = mapped_column(
        Text, primary_key=True, nullable=False
    )  # spectrumID from mzID
    spectra_data_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, nullable=False
    )
    upload_id: Mapped[str] = mapped_column(
        Integer,
        ForeignKey("upload.id"),
        primary_key=True,
        index=True,
        nullable=False,
    )
    peak_list_file_name: Mapped[str] = mapped_column(Text, nullable=False)
    precursor_mz: Mapped[float] = mapped_column(FLOAT, nullable=False)
    precursor_charge: Mapped[int] = mapped_column(SMALLINT, nullable=True)
    mz: Mapped[str] = mapped_column(LargeBinary, nullable=False)
    intensity: Mapped[str] = mapped_column(LargeBinary, nullable=False)
    retention_time: Mapped[float] = mapped_column(FLOAT, nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ["spectra_data_id", "upload_id"],
            ["spectradata.id", "spectradata.upload_id"],
        ),
    )

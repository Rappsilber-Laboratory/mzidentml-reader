from sqlalchemy import (
    FLOAT,
    REAL,
    SMALLINT,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, DOUBLE_PRECISION
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base

# Peak lists are native arrays in PostgreSQL (float8[] m/z, real[] intensity - the layout the
# xiview.org database has always used) and packed float64 blobs elsewhere (SQLite).
# DatabaseWriter converts values to whichever of the two the target column is.
MZ_ARRAY = LargeBinary().with_variant(ARRAY(DOUBLE_PRECISION), "postgresql")
INTENSITY_ARRAY = LargeBinary().with_variant(ARRAY(REAL), "postgresql")


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
    mz: Mapped[list] = mapped_column(MZ_ARRAY, nullable=False)
    intensity: Mapped[list] = mapped_column(INTENSITY_ARRAY, nullable=False)
    retention_time: Mapped[float] = mapped_column(FLOAT, nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ["spectra_data_id", "upload_id"],
            ["spectradata.id", "spectradata.upload_id"],
        ),
    )

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class SpectraData(Base):
    __tablename__ = "spectradata"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    upload_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("upload.id"),
        primary_key=True,
        index=True,
        nullable=False,
    )
    location: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=True)
    external_format_documentation: Mapped[str] = mapped_column(
        Text, nullable=True
    )
    file_format: Mapped[str] = mapped_column(Text, nullable=False)
    spectrum_id_format: Mapped[str] = mapped_column(Text, nullable=False)

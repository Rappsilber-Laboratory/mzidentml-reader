"""This file contains the DBSequence class, which is a SQLAlchemy model for the dbsequence table in the database."""

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class DBSequence(Base):
    __tablename__ = "dbsequence"
    upload_id: Mapped[str] = mapped_column(
        Integer, ForeignKey("upload.id"), primary_key=True, nullable=False
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    accession: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    sequence: Mapped[str] = mapped_column(Text, nullable=True)

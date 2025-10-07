from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class ProjectDetail(Base):
    __tablename__ = "projectdetails"
    id: Mapped[str] = mapped_column(
        Integer, primary_key=True, autoincrement=True, nullable=False
    )
    project_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    organism: Mapped[str] = mapped_column(Text, nullable=True)
    pubmed_id: Mapped[str] = mapped_column(Text, nullable=True)
    number_of_proteins: Mapped[int] = mapped_column(Integer, nullable=True)
    number_of_peptides: Mapped[int] = mapped_column(Integer, nullable=True)
    number_of_spectra: Mapped[int] = mapped_column(Integer, nullable=True)
    xiview_url: Mapped[str] = mapped_column(Text, nullable=True)
    pdb_ihm_url: Mapped[str] = mapped_column(Text, nullable=True)

    project_sub_details = relationship(
        "ProjectSubDetail",
        back_populates="project_detail",
        cascade="all, delete-orphan",
        single_parent=True,
    )

from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class ProjectSubDetail(Base):
    __tablename__ = "projectsubdetails"
    id: Mapped[str] = mapped_column(
        Integer, primary_key=True, autoincrement=True, nullable=False
    )
    project_detail_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projectdetails.id"), nullable=False
    )
    protein_db_ref: Mapped[str] = mapped_column(Text, nullable=False)
    protein_name: Mapped[str] = mapped_column(Text, nullable=True)
    gene_name: Mapped[str] = mapped_column(Text, nullable=True)
    protein_accession: Mapped[str] = mapped_column(Text, nullable=False)
    number_of_peptides: Mapped[int] = mapped_column(
        Integer, default=0, nullable=True
    )
    number_of_cross_links: Mapped[int] = mapped_column(
        Integer, default=0, nullable=True
    )
    in_pdbe_kb: Mapped[bool] = mapped_column(Boolean, nullable=False)
    in_alpha_fold_db: Mapped[bool] = mapped_column(Boolean, nullable=False)
    quote = False

    project_detail = relationship(
        "ProjectDetail", back_populates="project_sub_details"
    )

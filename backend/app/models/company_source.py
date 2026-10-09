"""
Association client ↔ source de scraping.

Une source (ONMP, TUNEPS, site universel) est scrapée UNE seule fois
par le pipeline. Chaque client choisit ensuite lesquelles il suit,
via cette table d'association.
"""

from app.core.time_utils import now_naive
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class CompanySource(Base):
    __tablename__ = "company_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)

    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_id = Column(
        Integer,
        ForeignKey("scraping_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    actif = Column(Boolean, default=True, nullable=False)

    created_at = Column(
        DateTime,
        default=now_naive,
        nullable=False,
    )

    company = relationship(
        "Company",
        back_populates="source_links",
    )

    source = relationship("ScrapingSource")

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "source_id",
            name="uq_company_source",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<CompanySource company_id={self.company_id} "
            f"source_id={self.source_id} actif={self.actif}>"
        )
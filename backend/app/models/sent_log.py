

from app.core.time_utils import now_naive
from sqlalchemy.orm import relationship
from app.core.database import Base
from sqlalchemy import (
    Column, DateTime, ForeignKey, Index, Integer, String, text,
)
class SentLog(Base):
    __tablename__ = "sent_log"
    __table_args__ = (
        Index(
            "uq_sent_log_company_tender_canal",
            "company_tender_id", "canal",
            unique=True,
            postgresql_where=text("company_tender_id IS NOT NULL"),
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Ancien champ — conservé, devient optionnel.
    sotradies_id = Column(
        String(64),
        ForeignKey("sotradies.id"),
        nullable=True,
    )

    # Nouveau champ — traçabilité par résultat client.
    company_tender_id = Column(
        Integer,
        ForeignKey("company_tenders.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    commercial = Column(String(255), nullable=False)
    canal = Column(String(20), nullable=False)  # "instantane" | "digest"
    date_envoi = Column(DateTime, default=now_naive, nullable=False)


    company_tender = relationship("CompanyTender")
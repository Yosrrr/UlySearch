"""Empêche qu'un même marché soit envoyé deux fois par email (Layer 8).

⚠️ Deux modes de traçabilité coexistent pendant la transition :
   - sotradies_id  : ancien mode mono-client (conservé pour compatibilité).
   - company_tender_id : nouveau mode multi-tenant, à utiliser
     désormais pour tous les nouveaux envois.
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class SentLog(Base):
    __tablename__ = "sent_log"

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
    date_envoi = Column(DateTime, default=datetime.utcnow, nullable=False)

    company_tender = relationship("CompanyTender")
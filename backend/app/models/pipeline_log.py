"""Traçabilité détaillée du pipeline de veille.

Chaque exécution du pipeline possède un run_id.
Chaque étape importante est enregistrée ici pour audit/debug :
scraping, filtrage date, déduplication, exclusion, IA, scoring,
assignation, insertion, erreur.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class PipelineLog(Base):
    __tablename__ = "pipeline_log"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Identifiant unique d'une exécution complète du pipeline
    run_id = Column(String(64), nullable=False, index=True)

    # Marché concerné si déjà connu/calculé
    tender_id = Column(String(64), nullable=True, index=True)

    # onmp, appeloffres, tuneps, etc.
    source = Column(String(50), nullable=True, index=True)

    # RUN_STARTED, SCRAPE_FINISHED, AI_RESULT, INSERTED, ERROR, etc.
    event_type = Column(String(50), nullable=False, index=True)

    # Message court lisible humainement
    message = Column(Text, nullable=True)

    # Détails techniques JSON sérialisables
    payload = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self) -> str:
        return (
            f"<PipelineLog run_id={self.run_id!r} "
            f"event={self.event_type!r} source={self.source!r}>"
        )
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Numeric
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class Sotradies(Base):
    __tablename__ = "sotradies"

    id = Column(String(64), primary_key=True)
    reference = Column(String(255), nullable=True)
    objet = Column(Text, nullable=False)
    acheteur = Column(String(500), nullable=False)
    categorie = Column(String(255), nullable=True)
    date_publication = Column(DateTime, nullable=True)
    date_limite = Column(DateTime, nullable=True)
    budget_estime = Column(Numeric(14, 2), nullable=True)
    source = Column(String(50), nullable=False)
    lien = Column(Text, nullable=False)
    date_detection = Column(DateTime, default=datetime.utcnow, nullable=False)
    raw_data = Column(JSONB, nullable=True)

    # --- Ajouts liés au workflow métier (notes de réunion, section 3) ---
    statut = Column(String(30), default="nouveau", nullable=False)
    # valeurs possibles : "nouveau" | "retenu" | "sans_suite"
    # jamais supprimé, conformément à la Règle 2 ("rien n'est perdu silencieusement")

    commercial_assigne = Column(String(255), nullable=True)
    score_details = Column(JSONB, nullable=True)
    
    acheteur_connu = Column(String(10), nullable=True)  # "Oui" | "Non" | None
    # ex: {"MATERIEL_ROULANT": 60, "ENGINS_TP": 0, ...} — mots-clés matchés inclus,
    # pour affichage dans le dashboard ("les mots-clés qui ont déclenché la détection")

    date_derniere_action = Column(DateTime, nullable=True)
    rappel_j3_envoye = Column(DateTime, nullable=True)
    rappel_j1_envoye = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Sotradies id={self.id} statut={self.statut} objet={self.objet[:40]!r}>"
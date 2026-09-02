"""Classe de base des scrapers HTTP classiques (requests / BeautifulSoup).

Contrat minimal commun à tous les scrapers du pipeline :
- un attribut `source_name` (utilisé par le cache, la config admin
  et le pipeline_log) ;
- une méthode `fetch_tenders()` retournant une liste de SotradiesRaw.

Les scrapers nécessitant un navigateur JavaScript (Scrapling) héritent
de ScraplingBaseScraper (base_scrapling.py), pas de cette classe.
"""
from abc import ABC, abstractmethod

from app.schemas.sotradies import SotradiesRaw


class BaseScraper(ABC):
    source_name: str = "base"

    @abstractmethod
    def fetch_tenders(self) -> list[SotradiesRaw]:
        """Retourne la liste des marchés bruts scrapés."""
        raise NotImplementedError
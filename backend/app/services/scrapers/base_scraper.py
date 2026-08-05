from abc import ABC, abstractmethod

from app.schemas.sotradies import SotradiesRaw


class BaseScraper(ABC):
    source_name: str

    @abstractmethod
    def fetch_tenders(self) -> list[SotradiesRaw]:
        raise NotImplementedError
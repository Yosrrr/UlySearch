"""Models package."""
"""
Point d'entrée unique des modèles SQLAlchemy.

Importer ce package (ou n'importe quel sous-module) garantit que
TOUS les modèles sont enregistrés avant toute résolution de
relation ORM. Cela évite les erreurs intermittentes
'failed to locate a name' qui dépendent de l'ordre d'import.

Ordre : d'abord les entités sans dépendance vers Company,
puis Company, puis les tables d'association qui en dépendent.
"""

from app.models.user import User  # noqa: F401,E402
from app.models.company import Company  # noqa: F401,E402
from app.models.commercial import Commercial  # noqa: F401,E402
from app.models.configuration import Configuration  # noqa: F401,E402
from app.models.scraping_source import ScrapingSource  # noqa: F401,E402
from app.models.sotradies import Sotradies  # noqa: F401,E402
from app.models.company_source import CompanySource  # noqa: F401,E402
from app.models.company_tender import CompanyTender  # noqa: F401,E402
from app.models.sent_log import SentLog  # noqa: F401,E402
from app.models.audit_log import AuditLog  # noqa: F401,E402
from app.models.known_buyer import KnownBuyer  # noqa: F401,E402
from app.models.system_action_log import SystemActionLog  # noqa: F401,E402
from app.models.pipeline_log import PipelineLog  # noqa: F401,E402

__all__ = [
    "User",
    "Company",
    "Commercial",
    "Configuration",
    "ScrapingSource",
    "Sotradies",
    "CompanySource",
    "CompanyTender",
    "SentLog",
    "AuditLog",
    "KnownBuyer",
    "SystemActionLog",
    "PipelineLog",
]
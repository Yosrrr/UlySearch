"""
Configuration Jinja2 centralisée pour les templates email.

Tous les emails doivent passer par cet environnement afin de garantir
l'autoescape HTML et éviter l'injection HTML via du contenu scrapé.
"""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.core.config import settings


jinja_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).resolve().parent.parent / "templates")),
    autoescape=select_autoescape(["html", "xml"]),
)
jinja_env.globals["app_name"] = settings.APP_NAME

def render_email(template_name: str, **context) -> str:
    """Rend un template email avec autoescape activé."""
    return jinja_env.get_template(template_name).render(**context)
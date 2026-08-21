"""
Configuration Jinja2 centralisée pour les templates email.

Tous les emails doivent passer par cet environnement afin de garantir
l'autoescape HTML et éviter l'injection HTML via du contenu scrapé.
"""
from jinja2 import Environment, FileSystemLoader, select_autoescape


jinja_env = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_email(template_name: str, **context) -> str:
    """Rend un template email avec autoescape activé."""
    return jinja_env.get_template(template_name).render(**context)
"""
Scraper pour l'Observatoire National des Marchés Publics (ONMP).
Source publique, aucun login nécessaire.

Le tableau des résultats est chargé en JavaScript après le chargement
de la page (confirmé en inspectant le HTML brut, qui contient la structure
du tableau mais aucune ligne). Playwright est donc nécessaire ici, comme
pour TUNEPS — un simple `requests` ne suffit pas.

Ce fichier inclut un mode debug : si le sélecteur du tableau ne correspond
pas à la vraie structure de la page, il sauvegarde une capture d'écran et
le HTML complet pour qu'on ajuste ensemble, plutôt que d'échouer en silence.
"""
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright
from dateutil import parser as date_parser

from app.services.scrapers.base_scraper import BaseScraper
from app.schemas.sotradies import SotradiesRaw

ONMP_LIST_URL = "https://www.marchespublics.gov.tn/fr/appels-doffres"
DEBUG_DIR = Path("debug_onmp")


class OnmpScraper(BaseScraper):
    source_name = "onmp"

    def fetch_tenders(self) -> list[SotradiesRaw]:
        results: list[SotradiesRaw] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )

            page.goto(ONMP_LIST_URL, wait_until="networkidle", timeout=60_000)

            # Laisse le temps au JS de charger les résultats.
            # Si le tableau utilise un sélecteur différent, on le verra
            # via le mode debug ci-dessous plutôt que de planter ici.
            try:
                page.wait_for_selector("table tbody tr", timeout=15_000)
            except Exception:
                self._save_debug(page)
                browser.close()
                raise RuntimeError(
                    "Aucune ligne de résultat détectée après 15s. "
                    "Voir debug_onmp/ (capture + HTML) pour ajuster le sélecteur."
                )

            rows = page.query_selector_all("table tbody tr")

            for row in rows:
                cells = row.query_selector_all("td")
                if len(cells) < 5:
                    continue  # ligne inattendue (en-tête, ligne vide...), on l'ignore

                texts = [c.inner_text().strip() for c in cells]
                # Ordre observé dans le HTML : Numéro AO | Acheteur public |
                # Objet | Date limite | Date de publication | PME
                reference, acheteur, objet, date_limite_raw, date_pub_raw = texts[:5]

                lien_el = row.query_selector("a")
                lien = lien_el.get_attribute("href") if lien_el else ONMP_LIST_URL
                if lien and lien.startswith("/"):
                    lien = f"https://www.marchespublics.gov.tn{lien}"

                try:
                    tender = SotradiesRaw(
                        reference=reference or None,
                        objet=objet,
                        acheteur=acheteur,
                        date_limite=self._safe_parse_date(date_limite_raw),
                        date_publication=self._safe_parse_date(date_pub_raw),
                        source=self.source_name,
                        lien=lien,
                    )
                    results.append(tender)
                except Exception as e:
                    # Une ligne malformée ne doit jamais faire planter tout le scraping
                    print(f"[onmp_scraper] Ligne ignorée (erreur de parsing) : {e}")
                    continue

            browser.close()

        return results

    @staticmethod
    def _safe_parse_date(raw: str) -> datetime | None:
        if not raw or not raw.strip():
            return None
        try:
            return date_parser.parse(raw.strip(), dayfirst=True)
        except Exception:
            return None

    @staticmethod
    def _save_debug(page) -> None:
        DEBUG_DIR.mkdir(exist_ok=True)
        page.screenshot(path=str(DEBUG_DIR / "onmp_liste.png"), full_page=True)
        (DEBUG_DIR / "onmp_liste.html").write_text(page.content(), encoding="utf-8")


if __name__ == "__main__":
    # Test manuel rapide : python -m app.services.scrapers.onmp_scraper
    scraper = OnmpScraper()
    tenders = scraper.fetch_tenders()
    print(f"{len(tenders)} marché(s) trouvé(s) sur ONMP")
    for t in tenders[:5]:
        print("-", t.objet[:80])
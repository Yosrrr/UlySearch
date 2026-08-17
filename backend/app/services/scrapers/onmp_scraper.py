"""
Scraper pour l'Observatoire National des Marchés Publics (ONMP).
Source publique, aucun login nécessaire.

Le site utilise DataTables en mode "serverSide" : la liste est en réalité
chargée via un appel AJAX (JSON) vers la même URL que la page, avec des
paramètres standards (start, length, columns[...]). On appelle cet
endpoint directement avec `requests`, sans Playwright ni clic sur un
bouton "page suivante" — beaucoup plus simple et rapide.

⚠️ Nécessite l'en-tête X-Requested-With: XMLHttpRequest, sinon le site
renvoie la page HTML complète au lieu du JSON attendu.
"""
from datetime import datetime

import requests
from dateutil import parser as date_parser

from app.services.scrapers.base_scraper import BaseScraper
from app.schemas.sotradies import SotradiesRaw

ONMP_URL = "https://www.marchespublics.gov.tn/fr/appels-doffres"
PAGE_SIZE = 50  # nombre de résultats demandés par appel


class OnmpScraper(BaseScraper):
    source_name = "onmp"

    def fetch_tenders(self) -> list[SotradiesRaw]:
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        })

        params = {
            "draw": 1,
            "start": 0,
            "length": PAGE_SIZE,
            "columns[0][data]": "id",
            "columns[1][data]": "organization.name_fr",
            "columns[2][data]": "title_fr",
            "columns[3][data]": "tenderPeriod_endDate",
            "columns[4][data]": "publication_date",
            "columns[5][data]": "reservedSME",
            "order[0][column]": 4,
            "order[0][dir]": "desc",
        }

        resp = session.get(ONMP_URL, params=params, timeout=30)
        resp.raise_for_status()

        try:
            data = resp.json()
        except ValueError:
            # Le site a renvoyé du HTML au lieu du JSON attendu — signale
            # clairement le problème plutôt que d'échouer en silence.
            with open("debug_onmp_raw_response.html", "w", encoding="utf-8") as f:
                f.write(resp.text)
            raise RuntimeError(
                "Réponse non-JSON reçue (voir debug_onmp_raw_response.html). "
                "Le site attend peut-être un en-tête ou un paramètre supplémentaire."
            )

        results = []
        for row in data.get("data", []):
            try:
                tender_id = row.get("id")  # déjà au format "Tender-103364"
                lien = f"{ONMP_URL}/{tender_id}" if tender_id else ONMP_URL

                tender = SotradiesRaw(
                    reference=tender_id,
                    objet=row.get("title_fr", "").strip(),
                    acheteur=(row.get("organization") or {}).get("name_fr", "").strip(),
                    date_limite=self._safe_parse_date(row.get("tenderPeriod_endDate")),
                    date_publication=self._safe_parse_date(row.get("publication_date")),
                    source=self.source_name,
                    lien=lien,
                )
                results.append(tender)
            except Exception as e:
                print(f"[onmp_scraper] Ligne ignorée (erreur de parsing) : {e}")
                continue

        print(f"[onmp_scraper] {len(results)} marché(s) récupéré(s) "
              f"(sur {data.get('recordsTotal', '?')} au total sur le site)")
        return results

    @staticmethod
    def _safe_parse_date(raw) -> datetime | None:
        if not raw:
            return None
        try:
            return date_parser.parse(str(raw), dayfirst=False)
        except Exception:
            return None


if __name__ == "__main__":
    scraper = OnmpScraper()
    tenders = scraper.fetch_tenders()
    print(f"\n{len(tenders)} marché(s) au total")
    for t in tenders[:5]:
        print("-", t.objet[:80])
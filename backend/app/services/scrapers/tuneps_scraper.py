"""
Scraper TUNEPS — API publique des avis d'appel d'offres.

Appelle directement l'endpoint JSON utilisé par le portail Angular :
    POST /api2/portail/bid/master/data

Avantages vs navigateur :
- pas de Playwright en production pour cette source ;
- rapide (~1 s par page de 100 avis) ;
- le nom de l'acheteur (bidInstNm) est PUBLIC → matching Layer 5 possible
  (contrairement à appeloffres.com).

Structure de réponse :
    {"code": "200", "payload": {"data": [...], "total": N}}
"""
import os
from datetime import datetime, timedelta

import certifi

# Windows : curl-cffi ne trouve pas toujours le magasin de certificats système.
# On pointe explicitement vers le bundle certifi (déjà dépendance du projet).
os.environ.setdefault("CURL_CA_BUNDLE", certifi.where())
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

from scrapling.fetchers import Fetcher  # noqa: E402

from app.schemas.sotradies import SotradiesRaw  # noqa: E402


API_URL = "https://www.tuneps.tn/api2/portail/bid/master/data"

# ⚠️ À CONFIRMER : cliquer sur un avis dans le portail et vérifier l'URL réelle.
# Fallback sûr : la page de listing publique.
DETAIL_URL = "https://www.tuneps.tn/portail/detail-offre?id={bid_id}"
FALLBACK_URL = "https://www.tuneps.tn/portail/offres"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://www.tuneps.tn",
    "Referer": "https://www.tuneps.tn/portail/offres",
}

PAGE_SIZE = 100
MAX_PAGES = 5          # garde-fou : 500 avis max par exécution
LOOKBACK_DAYS = 3      # arrêt dès que les avis dépassent cette ancienneté
REQUEST_TIMEOUT = 30   # secondes (curl-cffi compte en secondes)


def _parse_dt(raw: str | None) -> datetime | None:
    """Parse '2026-08-31 13:17:16.178341' ou '2026-09-30 10:00:00.0'."""
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _pick_objet(item: dict) -> str:
    """Préfère le libellé français, sinon anglais, sinon arabe.

    Normalise les retours à la ligne internes fréquents dans les
    intitulés TUNEPS.
    """
    for key in ("bidNmFr", "bidNmEn", "bidNmAr"):
        value = (item.get(key) or "").strip()
        if value:
            return " ".join(value.split())
    return ""


class TunepsScraper:
    source_name = "tuneps"

    def _fetch_page(self, offset: int) -> tuple[list[dict], int]:
        """Retourne (items, total). Lève une exception en cas d'échec HTTP."""
        payload = {
            "listSort": [],
            "dataSearch": [
                {"key": "publicYn", "value": "Y", "specificSearch": "="},
            ],
            "listCol": [],
            "pagination": {"offSet": offset, "limit": PAGE_SIZE},
            "sort": {"nameCol": "publicDt", "direction": "desc nulls last"},
        }

        response = Fetcher.post(
            API_URL,
            json=payload,
            headers=HEADERS,
            impersonate="chrome",
            timeout=REQUEST_TIMEOUT,
            verify=False  # Simule la signature réseau de Chrome
        )

        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} sur {API_URL}")

        data = response.json()
        inner = data.get("payload") or {}
        return inner.get("data") or [], int(inner.get("total") or 0)

    def parse_items(self, items: list[dict]) -> list[SotradiesRaw]:
        """Convertit les avis JSON TUNEPS en SotradiesRaw.

        Méthode séparée du réseau pour être testable avec une fixture
        locale (scripts/test_tuneps_parser.py).
        """
        tenders: list[SotradiesRaw] = []

        for item in items:
            try:
                objet = _pick_objet(item)
                if not objet:
                    continue

                bid_id = item.get("epBidMasterId")
                lien = (
                    DETAIL_URL.format(bid_id=bid_id)
                    if bid_id
                    else FALLBACK_URL
                )

                tenders.append(
                    SotradiesRaw(
                        source=self.source_name,
                        reference=str(item.get("bidNo") or ""),
                        objet=objet,
                        acheteur=(item.get("bidInstNm") or "Non communiqué").strip(),
                        categorie=None,  # déterminée ensuite par l'IA (Layer 4)
                        date_publication=_parse_dt(item.get("publicDt")),
                        date_limite=_parse_dt(item.get("bdRecvEndDt")),
                        budget_estime=None,
                        lien=lien,
                    )
                )
            except Exception as exc:
                # Un avis malformé ne doit jamais bloquer les autres.
                print(f"[tuneps] Avis ignoré (parsing) : {exc}")
                continue

        return tenders

    def fetch_tenders(self) -> list[SotradiesRaw]:
        """Récupère les avis récents (tri publicDt desc), avec pagination.

        S'arrête dès que la page contient des avis plus vieux que
        LOOKBACK_DAYS — le pipeline filtre ensuite sur la date exacte
        (filter_today_only), donc ce lookback couvre aussi les rattrapages
        après un week-end ou une panne.
        """
        cutoff = datetime.now() - timedelta(days=LOOKBACK_DAYS)
        all_tenders: list[SotradiesRaw] = []

        for page in range(MAX_PAGES):
            offset = page * PAGE_SIZE
            try:
                items, total = self._fetch_page(offset)
            except Exception as exc:
                print(f"[tuneps] ❌ Erreur page offset={offset} : {exc}")
                break

            if not items:
                break

            tenders = self.parse_items(items)
            all_tenders.extend(tenders)

            oldest = min(
                (t.date_publication for t in tenders if t.date_publication),
                default=None,
            )
            print(
                f"[tuneps] page offset={offset} : {len(tenders)} avis "
                f"(plus ancien : {oldest})"
            )

            if oldest and oldest < cutoff:
                break

        print(f"[tuneps] ✅ Total récupéré : {len(all_tenders)} avis")
        return all_tenders


if __name__ == "__main__":
    scraper = TunepsScraper()
    results = scraper.fetch_tenders()
    print()
    for t in results[:5]:
        pub = t.date_publication.date() if t.date_publication else "?"
        print(f"- [{t.reference}] {pub} | {t.objet[:55]} | {t.acheteur}")
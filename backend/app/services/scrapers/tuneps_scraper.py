"""
Scraper TUNEPS — API publique des avis d'appel d'offres.

POST /api2/portail/bid/master/data  ->  {"code": "200", "payload": {"data": [...], "total": N}}

Sécurité (F-021) :
- Par défaut : TLS non vérifié (tuneps.tn n'envoie pas son certificat
  intermédiaire) ET aucun identifiant envoyé. Lecture des annonces publiques.
- Sur le PC d'un client (essai clé USB) : TUNEPS_SSL_VERIFY=true
  (+ éventuellement TUNEPS_CA_BUNDLE=chemin\\vers\\chaine.pem).
  Les identifiants ne sont envoyés QUE si TLS est vérifié.
"""
import base64
import os
from datetime import datetime, timedelta

import certifi

# Windows : curl-cffi ne trouve pas toujours le magasin de certificats système.
os.environ.setdefault("CURL_CA_BUNDLE", certifi.where())
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

from scrapling.fetchers import Fetcher

from app.schemas.sotradies import SotradiesRaw

API_URL = "https://www.tuneps.tn/api2/portail/bid/master/data"

# ⚠️ À CONFIRMER : cliquer sur un avis dans le portail et vérifier l'URL réelle.
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
REQUEST_TIMEOUT = 30   # secondes


def _tls_verify():
    """
    False : TLS non vérifié (défaut, lecture publique).
    True  : vérification avec le magasin certifi.
    str   : chemin d'un fichier PEM (TUNEPS_CA_BUNDLE) contenant la chaîne complète.
    Lu à CHAQUE requête : le réglage peut changer sans redémarrer.
    """
    if os.getenv("TUNEPS_SSL_VERIFY", "false").strip().lower() not in ("1", "true", "yes"):
        return False
    bundle = os.getenv("TUNEPS_CA_BUNDLE", "").strip()
    return bundle if bundle else True


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
    """Libellé français, sinon anglais, sinon arabe (espaces normalisés)."""
    for key in ("bidNmFr", "bidNmEn", "bidNmAr"):
        value = (item.get(key) or "").strip()
        if value:
            return " ".join(value.split())
    return ""


class TunepsScraper:
    source_name = "tuneps"

    def __init__(self, auth=None):
        self.auth = auth

    def _build_headers(self, verify) -> dict:
        headers = dict(HEADERS)
        if self.auth and verify:
            token = base64.b64encode(
                f"{self.auth[0]}:{self.auth[1]}".encode("utf-8")
            ).decode("ascii")
            headers["Authorization"] = f"Basic {token}"
        elif self.auth:
            print("[tuneps] Identifiants ignorés : TLS non vérifié. "
                  "Activez TUNEPS_SSL_VERIFY=true sur le PC du client.")
        return headers

    def _fetch_page(self, offset: int) -> tuple[list[dict], int]:
        """Retourne (items, total). Lève une exception en cas d'échec HTTP."""
        payload = {
            "listSort": [],
            "dataSearch": [{"key": "publicYn", "value": "Y", "specificSearch": "="}],
            "listCol": [],
            "pagination": {"offSet": offset, "limit": PAGE_SIZE},
            "sort": {"nameCol": "publicDt", "direction": "desc nulls last"},
        }
        verify = _tls_verify()
        response = Fetcher.post(          # UNE seule requête par page
            API_URL,
            json=payload,
            headers=self._build_headers(verify),
            timeout=REQUEST_TIMEOUT,
            verify=verify,
        )
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} sur {API_URL}")

        data = response.json()
        inner = data.get("payload") or {}
        return inner.get("data") or [], int(inner.get("total") or 0)

    def parse_items(self, items: list[dict]) -> list[SotradiesRaw]:
        """Convertit les avis JSON TUNEPS en SotradiesRaw (testable sans réseau)."""
        tenders: list[SotradiesRaw] = []
        for item in items:
            try:
                objet = _pick_objet(item)
                if not objet:
                    continue
                bid_id = item.get("epBidMasterId")
                lien = DETAIL_URL.format(bid_id=bid_id) if bid_id else FALLBACK_URL
                tenders.append(
                    SotradiesRaw(
                        source=self.source_name,
                        reference=str(item.get("bidNo") or ""),
                        objet=objet,
                        acheteur=(item.get("bidInstNm") or "Non communiqué").strip(),
                        categorie=None,
                        date_publication=_parse_dt(item.get("publicDt")),
                        date_limite=_parse_dt(item.get("bdRecvEndDt")),
                        budget_estime=None,
                        lien=lien,
                    )
                )
            except Exception as exc:
                print(f"[tuneps] Avis ignoré (parsing) : {exc}")
        return tenders

    def fetch_tenders(self) -> list[SotradiesRaw]:
        """Avis récents (publicDt desc), pagination jusqu'à LOOKBACK_DAYS."""
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
            oldest = min((t.date_publication for t in tenders if t.date_publication), default=None)
            print(f"[tuneps] page offset={offset} : {len(tenders)} avis (plus ancien : {oldest}) total_api={total}")
            if oldest and oldest < cutoff:
                break

        print(f"[tuneps] ✅ Total récupéré : {len(all_tenders)} avis")
        return all_tenders


if __name__ == "__main__":
    for t in TunepsScraper().fetch_tenders()[:5]:
        pub = t.date_publication.date() if t.date_publication else "?"
        print(f"- [{t.reference}] {pub} | {t.objet[:55]} | {t.acheteur}")
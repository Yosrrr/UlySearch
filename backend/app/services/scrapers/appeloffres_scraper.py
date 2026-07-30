"""
Scraper pour appeloffres.com ("Tunisie Appel d'Offre").
Source publique pour la liste (objet, dates, catégorie) — l'acheteur
n'est PAS visible sans abonnement.

Structure observée : chaque avis a DEUX liens vers la même page de détail
(un badge à 2-3 lettres en début d'entrée, et un lien "Voir" en fin
d'entrée), avec le vrai titre en texte brut entre les deux. On remonte
donc à l'ancêtre commun des deux liens pour récupérer le bloc complet.
"""
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from app.services.scrapers.base_scraper import BaseScraper
from app.schemas.sotradies import SotradiesRaw

APPELOFFRES_BASE = "https://www.appeloffres.com"

# slug -> libellé affiché sur le site (sert de repère pour couper le texte)
CATEGORY_SLUGS = {
    "voitures-camions-et-engins": "Voitures camions et engins",
    "btp-tp": "BTP TP",
}

DATE_RE = re.compile(r"\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2}:\d{2})?")


class AppeloffresScraper(BaseScraper):
    source_name = "appeloffres"

    def fetch_tenders(self, max_pages_per_category: int = 2) -> list[SotradiesRaw]:
        results: list[SotradiesRaw] = []
        skipped = 0
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        })

        for slug, category_label in CATEGORY_SLUGS.items():
            for page in range(1, max_pages_per_category + 1):
                url = f"{APPELOFFRES_BASE}/appels-offres/{slug}"
                if page > 1:
                    url += f"?page={page}"

                resp = session.get(url, timeout=30)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")

                detail_links = soup.find_all(
                    "a", href=re.compile(rf"/appels-offres/{slug}/\d+-[a-z]+$")
                )
                if not detail_links:
                    break

                by_href: dict[str, list] = {}
                for link in detail_links:
                    href = link.get("href")
                    if href:
                        by_href.setdefault(href, []).append(link)

                page_has_recent = False

                for href, links in by_href.items():
                    objet = self._extract_objet(links, category_label)
                    if not objet or len(objet) < 3:
                        skipped += 1
                        continue

                    common = self._common_ancestor(links)
                    block_text = common.get_text(" ", strip=True) if common else ""

                    dates_found = DATE_RE.findall(block_text)
                    date_pub = self._safe_parse(dates_found[0]) if len(dates_found) >= 1 else None
                    date_limite = self._safe_parse(dates_found[-1]) if len(dates_found) >= 2 else None

                    # Marque si au moins une offre de cette page date d'aujourd'hui
                    if date_pub and date_pub.date() == datetime.now().date():
                        page_has_recent = True

                    full_link = href if href.startswith("http") else f"{APPELOFFRES_BASE}{href}"
                    ref_match = re.search(r"/(\d+-[a-z]+)$", href)
                    reference = ref_match.group(1) if ref_match else None

                    try:
                        tender = SotradiesRaw(
                            reference=reference,
                            objet=objet,
                            acheteur="Non communiqué (accès complet réservé aux abonnés)",
                            categorie=category_label,
                            date_publication=date_pub,
                            date_limite=date_limite,
                            source=self.source_name,
                            lien=full_link,
                        )
                        results.append(tender)
                    except Exception as e:
                        skipped += 1
                        print(f"[appeloffres_scraper] Ligne ignorée : {e}")

                # Les pages sont triées de la plus récente à la plus ancienne :
                # si aucune offre d'aujourd'hui sur cette page, inutile de
                # continuer vers les pages suivantes (encore plus anciennes)
                if not page_has_recent and page >= 1:
                    break

        print(f"[appeloffres_scraper] {len(results)} retenus, {skipped} ignorés")
        return results

    @staticmethod
    def _common_ancestor(links: list):
        """Remonte au plus petit ancêtre HTML commun à tous les liens donnés."""
        if len(links) == 1:
            return links[0].parent
        ancestors_first = list(links[0].parents)
        for anc in ancestors_first:
            if all(other in anc.descendants for other in links[1:]):
                return anc
        return links[0].parent

    def _extract_objet(self, links: list, category_label: str) -> str:
        common = self._common_ancestor(links)
        if not common:
            return ""
        block_text = common.get_text(" ", strip=True)

        idx = block_text.find(category_label)
        candidate = block_text[:idx].strip() if idx > 0 else block_text

        # 1) Retire d'abord le numéro de ligne isolé en tête (ex: "1 ", "23 ")
        candidate = re.sub(r"^\d+\s+", "", candidate).strip()

        # 2) PUIS retire le badge (texte du premier lien), maintenant en tête
        badge_text = links[0].get_text(strip=True)
        if badge_text and candidate.startswith(badge_text):
            candidate = candidate[len(badge_text):].strip()

        m = DATE_RE.search(candidate)
        if m:
            candidate = candidate[: m.start()].strip()

        return candidate

    @staticmethod
    def _safe_parse(raw: str):
        try:
            if len(raw) > 10:
                return datetime.strptime(raw, "%d/%m/%Y %H:%M:%S")
            return datetime.strptime(raw, "%d/%m/%Y")
        except Exception:
            return None


if __name__ == "__main__":
    scraper = AppeloffresScraper()
    tenders = scraper.fetch_tenders()
    print(f"\n{len(tenders)} marché(s) retenu(s) au total\n")
    for t in tenders[:15]:
        print("-", t.objet[:80], "|", t.date_limite)
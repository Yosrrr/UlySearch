from app.services.scrapers.universal_scraper import UniversalScraper

TESTS = [
    ("test_bad", "https://www.afdb.org/en/about-us/corporate-procurement/procurement-notices/current-solicitations", True, "Banque Africaine de Développement"),
    ("test_undp", "https://procurement-notices.undp.org/", False, "UNDP"),
]

for name, url, browser, buyer in TESTS:
    print("\n" + "=" * 70 + f"\n{name}\n" + "=" * 70)
    s = UniversalScraper(name, url, use_browser=browser, max_pages=1, default_buyer=buyer)
    results = s.fetch_tenders()
    for t in results[:8]:
        print(f"\n- {t.objet[:80]}")
        print(f"  ref : {t.reference} | pub : {t.date_publication} | limite : {t.date_limite}")
        print(f"  lien: {t.lien}")

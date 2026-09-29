"""Diagnostic TED : une requete publique, aucune ecriture en base."""

import json

import httpx


def main() -> int:
    endpoint = "https://api.ted.europa.eu/v3/notices/search"

    payload = {
        "query": "place-of-performance IN (LUX)",
        "fields": ["publication-number"],
        "limit": 3,
        "scope": "ACTIVE",
        "checkQuerySyntax": False,
        "paginationMode": "ITERATION",
    }

    try:
        with httpx.Client(
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=False,
        ) as client:
            response = client.post(
                endpoint,
                json=payload,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "VeilleAO-diagnostic/1.0",
                },
            )
    except httpx.RequestError as exc:
        print("Erreur reseau :", type(exc).__name__, str(exc))
        return 1

    print("HTTP :", response.status_code)
    print("Content-Type :", response.headers.get("content-type"))
    print("Allow :", response.headers.get("allow"))

    if response.status_code != 200:
        print("Debut de la reponse :")
        print(response.text[:1500])
        return 1

    try:
        data = response.json()
    except ValueError:
        print("La reponse n'est pas un JSON valide.")
        print(response.text[:1500])
        return 1

    print("Reponse JSON, apercu limite :")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
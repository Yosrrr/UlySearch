"""Renouvelle le certificat intermediaire Sectigo pour TUNEPS.

Usage : python scripts/renew_tuneps_cert.py
"""

import sys
import base64
from pathlib import Path

import httpx

AIA_URL = "http://crt.sectigo.com/SectigoPublicServerAuthenticationCADVR36.crt"

OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "app"
    / "certs"
    / "tuneps_chain.pem"
)


def main():
    print(f"Telechargement depuis {AIA_URL}...")

    response = httpx.get(AIA_URL, timeout=30, follow_redirects=True)
    response.raise_for_status()
    cert_der = response.content

    # Convertir le certificat DER en PEM
    cert_b64 = base64.b64encode(cert_der).decode("ascii")

    pem_lines = ["-----BEGIN CERTIFICATE-----"]

    for i in range(0, len(cert_b64), 64):
        pem_lines.append(cert_b64[i:i + 64])

    pem_lines.append("-----END CERTIFICATE-----")
    pem = "\n".join(pem_lines) + "\n"

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(pem, encoding="ascii")

    print(f"Certificat telecharge : {OUTPUT}")
    print(f"Taille : {len(pem)} octets")

    # Tester la connexion TLS avec le certificat telecharge
    try:
        with httpx.Client(
            verify=str(OUTPUT),
            timeout=15,
            follow_redirects=True,
        ) as client:
            response = client.get("https://www.tuneps.tn")

        print(f"Test TLS : HTTP {response.status_code}")

    except Exception as exc:
        print(f"Test TLS ECHEC : {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()

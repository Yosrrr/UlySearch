import httpx
import pytest
from app.services.scrapers.universal_scraper import _check_request


@pytest.mark.parametrize("url", ["http://127.0.0.1/", "http://169.254.169.254/latest", "http://10.0.0.5/"])
def test_adresse_interne_bloquee(url):
    with pytest.raises(httpx.RequestError):
        _check_request(httpx.Request("GET", url))

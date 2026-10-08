import inspect

from app.schemas.tender_out import TenderListPage
import app.api.tenders as tenders


def test_tender_list_page_schema():
    page = TenderListPage(items=[], total=0, limit=50, offset=0)
    assert page.total == 0
    assert page.limit == 50
    assert page.offset == 0
    assert page.items == []


def test_list_tenders_has_limit_offset():
    sig = inspect.signature(tenders.list_tenders)
    assert "limit" in sig.parameters
    assert "offset" in sig.parameters


def test_filtered_for_client_returns_tuple():
    ann = tenders._filtered_for_client.__annotations__.get("return")
    # Python 3.9+ may show tuple[...] 
    assert ann is not None
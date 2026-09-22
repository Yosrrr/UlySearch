from datetime import datetime, date
from app.services.pipeline import filter_today_only, _source_is_active


class Tender:
    def __init__(self, dp):
        self.date_publication = dp


def test_filter_today_only_keeps_only_target_date():
    tenders = [Tender(datetime(2026, 8, 21, 9)), Tender(datetime(2026, 8, 20, 9)), Tender(None)]
    kept, sans = filter_today_only(tenders, date(2026, 8, 21))
    assert len(kept) == 1
    assert sans == 1


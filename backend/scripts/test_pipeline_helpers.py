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


def test_source_is_active_with_current_keys():
    s = {"onmp": {"actif": True}, "appeloffres": {"actif": False}}
    assert _source_is_active(s, "onmp") is True
    assert _source_is_active(s, "appeloffres") is False


def test_source_is_active_with_legacy_keys():
    s = {"observatoire_national": {"actif": True}, "tunisie_appel_offre": {"actif": False}}
    assert _source_is_active(s, "onmp") is True
    assert _source_is_active(s, "appeloffres") is False


def test_source_is_active_when_no_config_defaults_to_true():
    assert _source_is_active({}, "onmp") is True
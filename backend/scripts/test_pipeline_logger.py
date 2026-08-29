from app.models.pipeline_log import PipelineLog
from app.services.pipeline_logger import log_pipeline_event


class FakeDB:
    def __init__(self):
        self.items = []
    def add(self, item):
        self.items.append(item)


def test_log_pipeline_event_adds_pipeline_log():
    db = FakeDB()
    log_pipeline_event(db, "run-test", "RUN_STARTED", source="onmp", tender_id="abc", message="test", payload={"x": 1})
    assert len(db.items) == 1
    item = db.items[0]
    assert isinstance(item, PipelineLog)
    assert item.run_id == "run-test"
    assert item.event_type == "RUN_STARTED"
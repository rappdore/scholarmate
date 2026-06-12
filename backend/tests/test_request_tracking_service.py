"""
Tests for RequestTrackingService stale-request purging (bug B-10).

register_request must opportunistically purge entries older than the max
request age so the registry is self-bounding even when a request is
registered but never completed.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

from app.services.request_tracking_service import RequestTrackingService


def make_stale(service: RequestTrackingService, request_id: str) -> None:
    """Backdate a registered request beyond the max request age."""
    service._active_requests[request_id].created_at = (
        datetime.now() - service._max_request_age - timedelta(minutes=1)
    )


class TestRegisterRequestPurgesStaleEntries:
    def test_stale_entry_purged_on_next_register(self):
        service = RequestTrackingService()
        stale_id = service.register_request("old.pdf", "pdf", page_num=1)
        make_stale(service, stale_id)

        new_id = service.register_request("new.pdf", "pdf", page_num=2)

        active = service.get_active_requests()
        assert stale_id not in active
        assert new_id in active

    def test_active_entry_not_purged(self):
        service = RequestTrackingService()
        active_id = service.register_request("recent.pdf", "pdf", page_num=1)

        new_id = service.register_request("new.epub", "epub", nav_id="ch1")

        active = service.get_active_requests()
        assert active_id in active
        assert new_id in active

    def test_stale_entry_task_cancelled_on_purge(self):
        service = RequestTrackingService()
        stale_id = service.register_request("old.pdf", "pdf", page_num=1)
        fake_task = MagicMock()
        service.set_request_task(stale_id, fake_task)
        make_stale(service, stale_id)

        service.register_request("new.pdf", "pdf", page_num=2)

        fake_task.cancel.assert_called_once()
        assert stale_id not in service.get_active_requests()

    def test_multiple_stale_entries_purged(self):
        service = RequestTrackingService()
        stale_ids = [
            service.register_request(f"old{i}.pdf", "pdf", page_num=i) for i in range(3)
        ]
        for request_id in stale_ids:
            make_stale(service, request_id)

        new_id = service.register_request("new.pdf", "pdf", page_num=9)

        active = service.get_active_requests()
        assert active.keys() == {new_id}

    def test_cleanup_old_requests_still_callable_directly(self):
        service = RequestTrackingService()
        stale_id = service.register_request("old.pdf", "pdf", page_num=1)
        make_stale(service, stale_id)

        removed = service.cleanup_old_requests()

        assert removed == 1
        assert service.get_active_requests() == {}

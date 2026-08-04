"""Run-lock + watermark-hold behavior for the WGR sync task (plan Task 5b).

Lock: unique owner token, compare-and-delete release, fail-closed only on
real connectivity errors. Watermark: manual partial pulls must never advance
the canonical cursor; held rows must be skipped when reading it back.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.tasks import wgr_sync


def test_lock_skips_when_held():
    fake = MagicMock()
    fake.set.return_value = None  # SET NX returns None when key exists
    with patch.object(wgr_sync, "_redis", return_value=fake):
        assert wgr_sync._acquire_lock("tok-a") is False


def test_lock_acquires_when_free():
    fake = MagicMock()
    fake.set.return_value = True
    with patch.object(wgr_sync, "_redis", return_value=fake):
        assert wgr_sync._acquire_lock("tok-a") is True
    fake.set.assert_called_once_with(
        wgr_sync.LOCK_KEY, "tok-a", nx=True, ex=wgr_sync.LOCK_TTL_SECONDS
    )


def test_lock_fails_closed_when_redis_down():
    with patch.object(wgr_sync, "_redis", side_effect=ConnectionError):
        assert wgr_sync._acquire_lock("tok-a") is False


def test_release_uses_compare_and_delete():
    fake = MagicMock()
    with patch.object(wgr_sync, "_redis", return_value=fake):
        wgr_sync._release_lock("tok-a")
    fake.eval.assert_called_once_with(
        wgr_sync._RELEASE_LUA, 1, wgr_sync.LOCK_KEY, "tok-a"
    )


def test_only_incremental_and_full_advance_watermark():
    # r7: a manual partial pull (since=<ISO>) repairs a window; it must never
    # advance the canonical cursor past unpulled history.
    assert wgr_sync.advances_watermark(None) is True
    assert wgr_sync.advances_watermark("full") is True
    assert wgr_sync.advances_watermark("2026-07-01T00:00:00+00:00") is False


def test_pick_watermark_skips_held_rows():
    # _read_watermark must walk past watermark-held rows (manual partial
    # pulls) to the latest row that actually carries a watermark — otherwise
    # one manual pull would trigger a surprise full pull of ~20 tables.
    ts = datetime(2026, 7, 26, 10, 0, tzinfo=timezone.utc)
    rows = [
        {"watermark_held": True, "since": "2026-07-25T00:00:00+00:00"},
        {"watermark": ts.isoformat(), "counts": {}},
        {"watermark": "2026-07-25T09:00:00+00:00"},
    ]
    assert wgr_sync.pick_watermark(rows) == ts


def test_pick_watermark_none_when_no_row_carries_one():
    assert wgr_sync.pick_watermark([{"watermark_held": True}, None, {}]) is None
    assert wgr_sync.pick_watermark([{"watermark": "not-a-date"}]) is None

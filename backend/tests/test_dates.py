from datetime import date

import pytest

from app.reporting.dates import resolve_report_range


def test_bangkok_dates_are_inclusive():
    value = resolve_report_range(date(2026, 7, 1), date(2026, 7, 2), "Asia/Bangkok")

    assert value.start_utc.isoformat() == "2026-06-30T17:00:00+00:00"
    assert value.end_exclusive_utc.isoformat() == "2026-07-02T17:00:00+00:00"


def test_rejects_reversed_range():
    with pytest.raises(ValueError, match="Ngày bắt đầu"):
        resolve_report_range(date(2026, 7, 2), date(2026, 7, 1), "Asia/Bangkok")

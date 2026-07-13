from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class UtcInterval:
    start_utc: datetime
    end_exclusive_utc: datetime


def resolve_report_range(start: date, end: date, timezone: str) -> UtcInterval:
    if start > end:
        raise ValueError("Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.")
    zone = ZoneInfo(timezone)
    return UtcInterval(
        start_utc=datetime.combine(start, time.min, zone).astimezone(UTC),
        end_exclusive_utc=datetime.combine(end + timedelta(days=1), time.min, zone).astimezone(UTC),
    )

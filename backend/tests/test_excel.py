from datetime import UTC, date, datetime

from app.reporting.excel import build_workbook
from app.reporting.service import ReportingService
from test_reporting import build_report


def test_workbook_matches_seven_sheet_contract():
    with build_report() as (db, page):
        dataset = ReportingService(db).build(page.id, date(2026, 7, 1), date(2026, 7, 2))

        workbook = build_workbook(dataset, datetime(2026, 7, 13, 1, tzinfo=UTC))

    assert workbook.sheetnames == [
        "Tổng quan",
        "Posts",
        "Insights",
        "Videos",
        "Định dạng",
        "Giờ đăng",
        "Comments",
    ]
    assert [cell.value for cell in workbook["Posts"][1]] == [
        "Created", "Message", "Media", "Reactions", "Like", "Love", "Haha",
        "Wow", "Sad", "Angry", "Care", "Comments", "Shares", "Engagement", "Permalink",
    ]
    assert workbook["Giờ đăng"].max_row == 25
    assert workbook["Posts"].freeze_panes == "A2"


def test_missing_insight_is_written_as_blank():
    with build_report() as (db, page):
        dataset = ReportingService(db).build(page.id, date(2026, 7, 1), date(2026, 7, 2))

        workbook = build_workbook(dataset, datetime.now(UTC))

    assert workbook["Insights"]["F2"].value is None

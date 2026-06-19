import csv
import importlib
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("FB_PAGE_ACCESS_TOKEN", "test-token")
fbcrawl = importlib.import_module("fbcrawl")


class FbCrawlAuditTest(unittest.TestCase):
    def test_configure_console_encoding_uses_utf8_when_reconfigure_is_available(self):
        class FakeStream:
            encoding = "cp1252"

            def __init__(self):
                self.requested_encoding = None

            def reconfigure(self, encoding=None):
                self.requested_encoding = encoding

        stdout = FakeStream()
        stderr = FakeStream()

        fbcrawl.configure_console_encoding(stdout, stderr)

        self.assertEqual(stdout.requested_encoding, "utf-8")
        self.assertEqual(stderr.requested_encoding, "utf-8")

    def test_sync_stores_posts_and_snapshots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "audit.db"
            posts = [
                {
                    "id": "page_1",
                    "message": "Hello",
                    "created_time": "2026-06-01T01:00:00+0000",
                    "permalink_url": "https://facebook.com/page/posts/1",
                    "full_picture": "https://example.com/a.jpg",
                    "reactions": {"summary": {"total_count": 2}},
                    "comments": {"summary": {"total_count": 3}},
                    "shares": {"count": 4},
                }
            ]

            synced = fbcrawl.sync_posts(
                db_path=db_path,
                since_date="2026-06-01",
                until_date="2026-06-02",
                fetcher=lambda since, until: posts,
            )

            self.assertEqual(synced.synced_count, 1)
            with closing(sqlite3.connect(db_path)) as conn:
                post_rows = conn.execute(
                    "select post_id, status, message from posts"
                ).fetchall()
                snapshot_rows = conn.execute(
                    "select post_id, reaction_count, comment_count, share_count from post_snapshots"
                ).fetchall()

            self.assertEqual(post_rows, [("page_1", "active", "Hello")])
            self.assertEqual(snapshot_rows, [("page_1", 2, 3, 4)])
            self.assertEqual(synced.deleted_by_snapshot, [])
            self.assertFalse(synced.stopped_by_limit)

    def test_sync_marks_missing_posts_deleted_after_complete_resync(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "audit.db"
            fbcrawl.sync_posts(
                db_path=db_path,
                since_date="2026-06-01",
                until_date="2026-06-08",
                fetcher=lambda since, until: [
                    {
                        "id": "page_1",
                        "message": "Will disappear",
                        "created_time": "2026-06-02T01:00:00+0000",
                        "permalink_url": "https://facebook.com/page/posts/1",
                    },
                    {
                        "id": "page_2",
                        "message": "Still here",
                        "created_time": "2026-06-03T01:00:00+0000",
                        "permalink_url": "https://facebook.com/page/posts/2",
                    },
                ],
            )

            result = fbcrawl.sync_posts(
                db_path=db_path,
                since_date="2026-06-01",
                until_date="2026-06-08",
                fetcher=lambda since, until: [
                    {
                        "id": "page_2",
                        "message": "Still here",
                        "created_time": "2026-06-03T01:00:00+0000",
                        "permalink_url": "https://facebook.com/page/posts/2",
                    }
                ],
            )

            self.assertEqual(result.deleted_by_snapshot, ["page_1"])
            with closing(sqlite3.connect(db_path)) as conn:
                rows = conn.execute(
                    "select post_id, status from posts order by post_id"
                ).fetchall()
                events = conn.execute(
                    "select post_id, source from deletion_events"
                ).fetchall()

            self.assertEqual(rows, [("page_1", "suspected_deleted"), ("page_2", "active")])
            self.assertEqual(events, [("page_1", "sync_snapshot")])

    def test_sync_limit_prevents_snapshot_delete_comparison(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "audit.db"
            fbcrawl.sync_posts(
                db_path=db_path,
                since_date="2026-06-01",
                until_date="2026-06-08",
                fetcher=lambda since, until: [
                    {
                        "id": "page_old",
                        "message": "Known before",
                        "created_time": "2026-06-02T01:00:00+0000",
                    }
                ],
            )

            result = fbcrawl.sync_posts(
                db_path=db_path,
                since_date="2026-06-01",
                until_date="2026-06-08",
                fetcher=lambda since, until, max_posts=None, sleep_seconds=None, progress_callback=None: fbcrawl.FetchResult(
                    posts=[
                        {
                            "id": "page_new",
                            "message": "New batch",
                            "created_time": "2026-06-03T01:00:00+0000",
                        }
                    ],
                    stopped_by_limit=True,
                    next_page_url="https://graph.facebook.com/next",
                ),
            )

            self.assertTrue(result.stopped_by_limit)
            self.assertEqual(result.deleted_by_snapshot, [])
            with closing(sqlite3.connect(db_path)) as conn:
                status = conn.execute(
                    "select status from posts where post_id = 'page_old'"
                ).fetchone()[0]
            self.assertEqual(status, "active")

    def test_fetch_posts_stops_at_limit_and_sleeps_between_pages(self):
        class FakeResponse:
            def __init__(self, payload):
                self.payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self.payload

        pages = [
            FakeResponse(
                {
                    "data": [{"id": f"page_{index}"} for index in range(100)],
                    "paging": {"next": "https://graph.facebook.com/next"},
                }
            ),
            FakeResponse(
                {
                    "data": [{"id": f"page_{index}"} for index in range(100, 200)],
                    "paging": {"next": "https://graph.facebook.com/last"},
                }
            ),
        ]

        with patch.object(fbcrawl.requests, "get", side_effect=pages) as get_mock:
            with patch.object(fbcrawl.time, "sleep") as sleep_mock:
                result = fbcrawl.fetch_posts_since_until(
                    "2026-06-01",
                    "2026-06-08",
                    access_token="token",
                    max_posts=150,
                    sleep_seconds=1.5,
                )

        self.assertEqual(len(result.posts), 150)
        self.assertTrue(result.stopped_by_limit)
        self.assertEqual(result.stopped_at_post_id, "page_149")
        self.assertEqual(get_mock.call_count, 2)
        sleep_mock.assert_called_once_with(1.5)

    def test_check_deleted_marks_missing_posts_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "audit.db"
            fbcrawl.sync_posts(
                db_path=db_path,
                since_date="2026-06-01",
                until_date="2026-06-02",
                fetcher=lambda since, until: [
                    {
                        "id": "page_1",
                        "message": "Deleted later",
                        "created_time": "2026-06-01T01:00:00+0000",
                        "permalink_url": "https://facebook.com/page/posts/1",
                    }
                ],
            )

            deleted = fbcrawl.check_deleted_posts(
                db_path=db_path,
                post_checker=lambda post_id: False,
            )
            deleted_again = fbcrawl.check_deleted_posts(
                db_path=db_path,
                post_checker=lambda post_id: False,
            )

            self.assertEqual(deleted, ["page_1"])
            self.assertEqual(deleted_again, [])
            with closing(sqlite3.connect(db_path)) as conn:
                status = conn.execute(
                    "select status from posts where post_id = 'page_1'"
                ).fetchone()[0]
                deletion_count = conn.execute("select count(*) from deletion_events").fetchone()[0]

            self.assertEqual(status, "suspected_deleted")
            self.assertEqual(deletion_count, 1)

    def test_check_deleted_filters_by_own_date_range(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "audit.db"
            fbcrawl.sync_posts(
                db_path=db_path,
                since_date="2026-06-01",
                until_date="2026-06-10",
                fetcher=lambda since, until: [
                    {
                        "id": "page_early",
                        "message": "Outside range",
                        "created_time": "2026-06-02T01:00:00+0000",
                    },
                    {
                        "id": "page_late",
                        "message": "Inside range",
                        "created_time": "2026-06-08T01:00:00+0000",
                    },
                ],
            )

            checked = []
            deleted = fbcrawl.check_deleted_posts(
                db_path=db_path,
                since_date="2026-06-07",
                until_date="2026-06-09",
                post_checker=lambda post_id: checked.append(post_id) or False,
                sleep_seconds=0,
            )

            self.assertEqual(checked, ["page_late"])
            self.assertEqual(deleted, ["page_late"])
            with closing(sqlite3.connect(db_path)) as conn:
                rows = conn.execute(
                    "select post_id, status from posts order by post_id"
                ).fetchall()
            self.assertEqual(rows, [("page_early", "active"), ("page_late", "suspected_deleted")])

    def test_check_deleted_rejects_range_longer_than_one_week(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "audit.db"

            with self.assertRaisesRegex(ValueError, "không được vượt quá 7 ngày"):
                fbcrawl.check_deleted_posts(
                    db_path=db_path,
                    since_date="2026-06-01",
                    until_date="2026-06-09",
                    post_checker=lambda post_id: True,
                )

    def test_check_deleted_stops_after_200_requests_and_warns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "audit.db"
            fbcrawl.sync_posts(
                db_path=db_path,
                since_date="2026-06-01",
                until_date="2026-06-08",
                fetcher=lambda since, until: [
                    {
                        "id": f"page_{index}",
                        "message": f"Post {index}",
                        "created_time": "2026-06-02T01:00:00+0000",
                    }
                    for index in range(201)
                ],
                max_posts=0,
            )

            checked = []
            result = fbcrawl.check_deleted_posts(
                db_path=db_path,
                since_date="2026-06-01",
                until_date="2026-06-08",
                post_checker=lambda post_id: checked.append(post_id) or True,
                sleep_seconds=0,
            )

            self.assertEqual(len(checked), 200)
            self.assertEqual(result.checked_count, 200)
            self.assertTrue(result.stopped_by_limit)
            self.assertIn("200", result.warning)

    def test_export_report_writes_audit_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "audit.db"
            report_path = Path(temp_dir) / "audit.csv"
            fbcrawl.sync_posts(
                db_path=db_path,
                since_date="2026-06-01",
                until_date="2026-06-02",
                fetcher=lambda since, until: [
                    {
                        "id": "page_1",
                        "message": "Report me",
                        "created_time": "2026-06-01T01:00:00+0000",
                        "permalink_url": "https://facebook.com/page/posts/1",
                    }
                ],
            )

            count = fbcrawl.export_report(db_path=db_path, csv_path=report_path)

            self.assertEqual(count, 1)
            with open(report_path, encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))

            self.assertEqual(rows[0]["post_id"], "page_1")
            self.assertEqual(rows[0]["status"], "active")
            self.assertEqual(rows[0]["message"], "Report me")
            self.assertNotIn("T", rows[0]["created_time"])
            self.assertNotIn("Z", rows[0]["created_time"])
            self.assertRegex(rows[0]["created_time"], r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}")


if __name__ == "__main__":
    unittest.main()

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.graph.client import GraphAPIError, GraphClient
from app.graph.metrics import METRICS
from app.models import JobStatus, MetricAvailability, MetricStatus, Page, PageDailyInsight, Post, PostSnapshot, SyncJob, Video


def parse_graph_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def count_summary(raw: dict, name: str) -> int | None:
    summary = raw.get(name, {}).get("summary", {})
    return summary.get("total_count")


def normalize_media_type(raw: dict) -> str:
    attachment = (raw.get("attachments", {}).get("data") or [{}])[0]
    kind = str(attachment.get("type") or "").lower()
    if "album" in kind:
        return "album"
    if "photo" in kind:
        return "photo"
    if "video" in kind:
        return "video"
    if "link" in kind or attachment.get("url"):
        return "link"
    return "status/other"


class SyncService:
    def __init__(self, db: Session, graph: GraphClient):
        self.db = db
        self.graph = graph

    def run(self, job_id: int) -> None:
        job = self.db.get(SyncJob, job_id)
        if job is None:
            raise LookupError("Không tìm thấy job.")
        page = self.db.get(Page, job.page_id)
        if page is None:
            raise LookupError("Không tìm thấy Page.")
        start = datetime.combine(job.start_date, time.min, ZoneInfo(page.timezone)).astimezone(UTC)
        end = datetime.combine(job.end_date + timedelta(days=1), time.min, ZoneInfo(page.timezone)).astimezone(UTC)
        captured_at = datetime.now(UTC)
        try:
            self._sync_posts(page, start, end, captured_at, job)
            self._sync_insights(page, start, end, captured_at)
            self._sync_videos(page, start, end, captured_at)
        except GraphAPIError as exc:
            if exc.kind in {"transient", "rate_limit"}:
                job.status = JobStatus.retrying
                job.next_attempt_at = datetime.now(UTC) + timedelta(minutes=5)
            else:
                job.status = JobStatus.failed
            job.error_code = exc.kind
            job.error_message = str(exc)
            self.db.commit()
            return
        if job.status == JobStatus.cancelling:
            job.status = JobStatus.cancelled
        else:
            job.status = JobStatus.completed
            page.latest_sync_at = captured_at
        job.lease_expires_at = None
        self.db.commit()

    def _sync_posts(self, page: Page, start: datetime, end: datetime, captured_at: datetime, job: SyncJob) -> None:
        for raw in self.graph.iter_posts(page.external_page_id, start, end):
            if job.status == JobStatus.cancelling:
                break
            post = self.db.scalar(select(Post).where(Post.page_id == page.id, Post.external_post_id == raw["id"]))
            if post is None:
                post = Post(page_id=page.id, external_post_id=raw["id"])
                self.db.add(post)
            post.published_at = parse_graph_time(raw.get("created_time"))
            post.message = raw.get("message")
            post.media_type = normalize_media_type(raw)
            post.permalink = raw.get("permalink_url")
            post.reactions = count_summary(raw, "reactions")
            post.comment_count = count_summary(raw, "comments")
            post.share_count = raw.get("shares", {}).get("count")
            post.captured_at = captured_at
            self.db.flush()
            self.db.add(PostSnapshot(post_id=post.id, captured_at=captured_at, reactions=post.reactions, comments=post.comment_count, shares=post.share_count))
            job.progress_current += 1
            if job.progress_current % 100 == 0:
                self.db.commit()
        self.db.commit()

    def _sync_insights(self, page: Page, start: datetime, end: datetime, captured_at: datetime) -> None:
        for logical_name, definition in METRICS.items():
            try:
                rows = list(self.graph.iter_insights(page.external_page_id, definition.candidates, start, end))
            except GraphAPIError as exc:
                self._set_metric_status(page.id, logical_name, MetricStatus.unavailable, str(exc), captured_at)
                continue
            self._set_metric_status(page.id, logical_name, MetricStatus.available, None, captured_at)
            for metric in rows:
                source_name = metric.get("name") or definition.candidates[0]
                for point in metric.get("values", []):
                    day = parse_graph_time(point.get("end_time"))
                    if day is None:
                        continue
                    existing = self.db.scalar(select(PageDailyInsight).where(PageDailyInsight.page_id == page.id, PageDailyInsight.metric_date == day.date(), PageDailyInsight.metric_name == logical_name, PageDailyInsight.period == definition.period, PageDailyInsight.source_version == source_name))
                    if existing is None:
                        existing = PageDailyInsight(page_id=page.id, metric_date=day.date(), metric_name=logical_name, period=definition.period, source_version=source_name)
                        self.db.add(existing)
                    value = point.get("value")
                    existing.value = Decimal(str(value)) if isinstance(value, (int, float)) else None
                    existing.captured_at = captured_at
        self.db.commit()

    def _set_metric_status(self, page_id: int, name: str, status: MetricStatus, reason: str | None, checked_at: datetime) -> None:
        version = "logical"
        value = self.db.scalar(select(MetricAvailability).where(MetricAvailability.page_id == page_id, MetricAvailability.metric_name == name, MetricAvailability.source_version == version))
        if value is None:
            value = MetricAvailability(page_id=page_id, metric_name=name, source_version=version)
            self.db.add(value)
        value.status = status
        value.reason = reason
        value.checked_at = checked_at
        if status == MetricStatus.available:
            value.last_success_at = checked_at

    def _sync_videos(self, page: Page, start: datetime, end: datetime, captured_at: datetime) -> None:
        for raw in self.graph.iter_videos(page.external_page_id, start, end):
            video = self.db.scalar(select(Video).where(Video.page_id == page.id, Video.external_video_id == raw["id"]))
            if video is None:
                video = Video(page_id=page.id, external_video_id=raw["id"])
                self.db.add(video)
            video.title = raw.get("title") or raw.get("description")
            video.published_at = parse_graph_time(raw.get("created_time"))
            video.length_seconds = raw.get("length")
            video.permalink = raw.get("permalink_url")
            video.captured_at = captured_at
        self.db.commit()

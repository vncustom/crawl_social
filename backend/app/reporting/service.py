from datetime import date, timedelta
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Comment, Page, PageDailyInsight, Post, SyncJob, Video
from app.reporting.dates import resolve_report_range


def number(value) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


class ReportSummary(BaseModel):
    posts: int
    reactions: int
    comments: int
    shares: int
    total_engagement: int
    average_engagement: float
    current_followers: int | None
    follower_growth: int | None


class PostRow(BaseModel):
    external_post_id: str
    created: object | None
    message: str | None
    media: str
    reactions: int
    like: int
    love: int
    haha: int
    wow: int
    sad: int
    angry: int
    care: int
    comments: int
    shares: int
    engagement: int
    permalink: str | None


class DailyPostRow(BaseModel):
    metric_date: date
    posts: int = 0
    reactions: int = 0
    comments: int = 0
    shares: int = 0
    engagement: int = 0


class DailyInsightRow(BaseModel):
    metric_date: date
    daily_new_followers: float | int | None = None
    followers_total: float | int | None = None
    post_engagements: float | int | None = None
    video_views: float | int | None = None
    page_views: float | int | None = None


class FormatRow(BaseModel):
    media: str
    posts: int
    average_engagement: float
    total_engagement: int
    reactions: int
    comments: int
    shares: int


class ReportDataset(BaseModel):
    page_id: int
    external_page_id: str
    page_name: str
    category: str | None
    link: str | None
    start_date: date
    end_date: date
    summary: ReportSummary
    posts: list[PostRow]
    daily_posts: list[DailyPostRow]
    daily_insights: list[DailyInsightRow]
    top_posts: list[PostRow]
    formats: list[FormatRow]
    posting_hours: list[list[int]]
    videos: list[dict]
    comments_detail: list[dict]
    latest_sync_at: object | None
    active_job_id: int | None


class ReportingService:
    def __init__(self, db: Session):
        self.db = db

    def build(self, page_id: int, start: date, end: date) -> ReportDataset:
        page = self.db.get(Page, page_id)
        if page is None:
            raise LookupError("Không tìm thấy Page.")
        interval = resolve_report_range(start, end, page.timezone)
        source_posts = self.db.scalars(
            select(Post).where(
                Post.page_id == page.id,
                Post.published_at >= interval.start_utc,
                Post.published_at < interval.end_exclusive_utc,
            ).order_by(Post.published_at.desc(), Post.external_post_id)
        ).all()
        posts = [self._post_row(post) for post in source_posts]
        reactions = sum(row.reactions for row in posts)
        comments = sum(row.comments for row in posts)
        shares = sum(row.shares for row in posts)
        total = reactions + comments + shares
        current = self._follower_value(page.id, end, before=False)
        baseline = self._follower_value(page.id, start, before=True)
        summary = ReportSummary(
            posts=len(posts), reactions=reactions, comments=comments, shares=shares,
            total_engagement=total, average_engagement=round(total / len(posts), 1) if posts else 0,
            current_followers=current, follower_growth=(current - baseline) if current is not None and baseline is not None else None,
        )
        daily_posts = self._daily_posts(start, end, source_posts, page.timezone)
        daily_insights = self._daily_insights(page.id, start, end)
        formats = self._formats(posts)
        posting_hours = [[0 for _ in range(7)] for _ in range(24)]
        from zoneinfo import ZoneInfo
        for post in source_posts:
            if post.published_at:
                local = post.published_at.astimezone(ZoneInfo(page.timezone))
                posting_hours[local.hour][local.weekday()] += 1
        active = self.db.scalar(select(SyncJob).where(SyncJob.page_id == page.id, SyncJob.status.in_(["queued", "running", "retrying", "cancelling"])))
        videos = [self._video_dict(v) for v in self.db.scalars(select(Video).where(Video.page_id == page.id, Video.published_at >= interval.start_utc, Video.published_at < interval.end_exclusive_utc))]
        comments_detail = [self._comment_dict(c) for c in self.db.scalars(select(Comment).where(Comment.page_id == page.id, Comment.published_at >= interval.start_utc, Comment.published_at < interval.end_exclusive_utc))]
        return ReportDataset(
            page_id=page.id, external_page_id=page.external_page_id, page_name=page.display_name, category=page.category, link=page.public_link,
            start_date=start, end_date=end, summary=summary, posts=posts, daily_posts=daily_posts, daily_insights=daily_insights,
            top_posts=sorted(posts, key=lambda row: (-row.engagement, -(row.created.timestamp() if row.created else 0), row.external_post_id))[:5],
            formats=formats, posting_hours=posting_hours, videos=videos, comments_detail=comments_detail,
            latest_sync_at=page.latest_sync_at, active_job_id=active.id if active else None,
        )

    def _post_row(self, post: Post) -> PostRow:
        reactions = post.reactions or 0
        comments = post.comment_count or 0
        shares = post.share_count or 0
        return PostRow(external_post_id=post.external_post_id, created=post.published_at, message=post.message, media=post.media_type,
            reactions=reactions, like=post.like_count or 0, love=post.love_count or 0, haha=post.haha_count or 0, wow=post.wow_count or 0,
            sad=post.sad_count or 0, angry=post.angry_count or 0, care=post.care_count or 0, comments=comments, shares=shares,
            engagement=reactions + comments + shares, permalink=post.permalink)

    def _follower_value(self, page_id: int, boundary: date, before: bool) -> int | None:
        condition = PageDailyInsight.metric_date < boundary if before else PageDailyInsight.metric_date <= boundary
        row = self.db.scalar(select(PageDailyInsight).where(PageDailyInsight.page_id == page_id, PageDailyInsight.metric_name == "followers_total", condition).order_by(PageDailyInsight.metric_date.desc()))
        return int(row.value) if row and row.value is not None else None

    def _daily_posts(self, start: date, end: date, posts, timezone: str) -> list[DailyPostRow]:
        from zoneinfo import ZoneInfo
        rows = {start + timedelta(days=i): DailyPostRow(metric_date=start + timedelta(days=i)) for i in range((end-start).days+1)}
        for post in posts:
            day = post.published_at.astimezone(ZoneInfo(timezone)).date()
            row = rows[day]; row.posts += 1; row.reactions += post.reactions or 0; row.comments += post.comment_count or 0; row.shares += post.share_count or 0; row.engagement = row.reactions + row.comments + row.shares
        return list(rows.values())

    def _daily_insights(self, page_id: int, start: date, end: date) -> list[DailyInsightRow]:
        rows = {start + timedelta(days=i): DailyInsightRow(metric_date=start + timedelta(days=i)) for i in range((end-start).days+1)}
        for item in self.db.scalars(select(PageDailyInsight).where(PageDailyInsight.page_id == page_id, PageDailyInsight.metric_date >= start, PageDailyInsight.metric_date <= end)):
            if item.metric_name in DailyInsightRow.model_fields:
                setattr(rows[item.metric_date], item.metric_name, number(item.value))
        return list(rows.values())

    def _formats(self, posts: list[PostRow]) -> list[FormatRow]:
        result = []
        for media in sorted({p.media for p in posts}):
            group = [p for p in posts if p.media == media]; total = sum(p.engagement for p in group)
            result.append(FormatRow(media=media, posts=len(group), average_engagement=round(total/len(group),1), total_engagement=total, reactions=sum(p.reactions for p in group), comments=sum(p.comments for p in group), shares=sum(p.shares for p in group)))
        return result

    @staticmethod
    def _video_dict(video: Video) -> dict:
        return {"title": video.title, "created": video.published_at, "length_seconds": number(video.length_seconds), "views": video.views, "average_watch_time": number(video.average_watch_time), "complete_views": video.complete_views, "permalink": video.permalink}

    @staticmethod
    def _comment_dict(comment: Comment) -> dict:
        return {"created": comment.published_at, "post_excerpt": comment.post_excerpt, "message": comment.message, "author": comment.author_label, "likes": comment.likes or 0, "replies": comment.replies or 0}

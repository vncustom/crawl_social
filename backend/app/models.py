from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class JobType(str, enum.Enum):
    daily = "daily"
    manual = "manual"
    backfill = "backfill"


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    retrying = "retrying"
    cancelling = "cancelling"
    completed = "completed"
    cancelled = "cancelled"
    failed = "failed"


class MetricStatus(str, enum.Enum):
    available = "available"
    unavailable = "unavailable"
    unknown = "unknown"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Page(TimestampMixin, Base):
    __tablename__ = "pages"
    id: Mapped[int] = mapped_column(primary_key=True)
    external_page_id: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(255))
    public_link: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Bangkok")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    daily_sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    latest_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdminUser(TimestampMixin, Base):
    __tablename__ = "admin_users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(128), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(32), default="admin")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdminSession(Base):
    __tablename__ = "admin_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class SyncJob(TimestampMixin, Base):
    __tablename__ = "sync_jobs"
    __table_args__ = (
        Index(
            "uq_active_job_per_page",
            "page_id",
            unique=True,
            postgresql_where=text("status IN ('queued','running','retrying','cancelling')"),
            sqlite_where=text("status IN ('queued','running','retrying','cancelling')"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), index=True)
    job_type: Mapped[JobType] = mapped_column(Enum(JobType))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.queued)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    checkpoint: Mapped[str | None] = mapped_column(Text)
    progress_current: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int | None] = mapped_column(Integer)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    worker_id: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Post(TimestampMixin, Base):
    __tablename__ = "posts"
    __table_args__ = (UniqueConstraint("page_id", "external_post_id", name="uq_page_post"), Index("ix_posts_page_created", "page_id", "published_at"))
    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"))
    external_post_id: Mapped[str] = mapped_column(String(128))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    message: Mapped[str | None] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(32), default="status/other")
    permalink: Mapped[str | None] = mapped_column(Text)
    reactions: Mapped[int | None] = mapped_column(Integer)
    like_count: Mapped[int | None] = mapped_column(Integer)
    love_count: Mapped[int | None] = mapped_column(Integer)
    haha_count: Mapped[int | None] = mapped_column(Integer)
    wow_count: Mapped[int | None] = mapped_column(Integer)
    sad_count: Mapped[int | None] = mapped_column(Integer)
    angry_count: Mapped[int | None] = mapped_column(Integer)
    care_count: Mapped[int | None] = mapped_column(Integer)
    comment_count: Mapped[int | None] = mapped_column(Integer)
    share_count: Mapped[int | None] = mapped_column(Integer)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PostSnapshot(Base):
    __tablename__ = "post_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reactions: Mapped[int | None] = mapped_column(Integer)
    comments: Mapped[int | None] = mapped_column(Integer)
    shares: Mapped[int | None] = mapped_column(Integer)


class PageDailyInsight(Base):
    __tablename__ = "page_daily_insights"
    __table_args__ = (UniqueConstraint("page_id", "metric_date", "metric_name", "period", "source_version", name="uq_daily_metric"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), index=True)
    metric_date: Mapped[date] = mapped_column(Date)
    metric_name: Mapped[str] = mapped_column(String(128))
    period: Mapped[str] = mapped_column(String(32))
    source_version: Mapped[str] = mapped_column(String(32))
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Video(TimestampMixin, Base):
    __tablename__ = "videos"
    __table_args__ = (UniqueConstraint("page_id", "external_video_id", name="uq_page_video"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"))
    external_video_id: Mapped[str] = mapped_column(String(128))
    title: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    length_seconds: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    views: Mapped[int | None] = mapped_column(Integer)
    average_watch_time: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    complete_views: Mapped[int | None] = mapped_column(Integer)
    permalink: Mapped[str | None] = mapped_column(Text)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Comment(TimestampMixin, Base):
    __tablename__ = "comments"
    __table_args__ = (UniqueConstraint("page_id", "external_comment_id", name="uq_page_comment"), Index("ix_comments_page_created", "page_id", "published_at"))
    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"))
    post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    external_comment_id: Mapped[str] = mapped_column(String(128))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    post_excerpt: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    author_label: Mapped[str] = mapped_column(String(255), default="(ẩn)")
    likes: Mapped[int | None] = mapped_column(Integer)
    replies: Mapped[int | None] = mapped_column(Integer)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MetricAvailability(TimestampMixin, Base):
    __tablename__ = "metric_availability"
    __table_args__ = (UniqueConstraint("page_id", "metric_name", "source_version", name="uq_metric_availability"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"))
    metric_name: Mapped[str] = mapped_column(String(128))
    source_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[MetricStatus] = mapped_column(Enum(MetricStatus), default=MetricStatus.unknown)
    reason: Mapped[str | None] = mapped_column(Text)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    action: Mapped[str] = mapped_column(String(128), index=True)
    target_type: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[str | None] = mapped_column(String(128))
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

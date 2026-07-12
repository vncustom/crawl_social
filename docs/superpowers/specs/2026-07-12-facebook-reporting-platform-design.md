# Facebook Reporting Platform Design

**Date:** 2026-07-12
**Status:** Approved
**Reference files:** `Sample_Report.xlsx`, `Báo cáo FB thang-1.JPG`, `Báo cáo FB thang-5.JPG`

## 1. Goal

Build a web-first reporting platform for multiple Facebook Pages. An administrator manually registers Page IDs, the system collects Page data into PostgreSQL, and an authenticated dashboard displays reports for a selected Page and reporting period. The same stored data must produce an Excel workbook matching the seven-sheet structure of `Sample_Report.xlsx`.

The default Page ID is `1125132200689307`. The server reads the shared Page Access Token only from `FB_PAGE_ACCESS_TOKEN`.

## 2. Scope

### Version 1

- One authenticated administrator account.
- Manual Page ID management: add, edit display metadata, enable, disable, sync now, and backfill.
- Default Page record for `1125132200689307`.
- One shared `FB_PAGE_ACCESS_TOKEN` for all Pages.
- Daily scheduled synchronization and manual synchronization per Page.
- Automatic 90-day backfill for a newly added Page, with an administrator-selectable custom backfill range.
- Dashboard filters for Page, start date, and end date.
- Default reporting period from one calendar month before today through today, inclusive.
- Daily KPI charts, daily Page Insights chart, top-post ranking, and Excel export.
- Docker Compose deployment with a web process, worker process, and PostgreSQL.

### Deferred

- Multiple users, roles, and Page-level authorization.
- Separate access tokens per Page.
- Cross-Page comparison dashboards.
- Distributed workers and queue scaling.
- Email, Slack, or other external notifications.

The schema may retain a simple role field and Page ownership boundaries so deferred authorization can be introduced without redesigning reporting data.

## 3. Architecture

The platform uses four logical components:

1. **Web frontend:** an authenticated dashboard and administration interface. It never calls Meta Graph API directly.
2. **FastAPI application:** authentication, Page administration, report queries, job control, and streamed Excel downloads.
3. **Worker and scheduler:** Graph API collection, daily synchronization, backfill, retry, checkpointing, and metric availability checks.
4. **PostgreSQL:** the single source of truth for Pages, collected facts, snapshots, jobs, and audit history.

The dashboard and Excel exporter share one reporting service. KPI formulas, date boundaries, missing-data behavior, and media-type normalization must therefore be implemented once and reused by both outputs.

For the initial deployment, the scheduler and background worker may use a PostgreSQL-backed job table and row locking. A separate message broker is unnecessary until workload measurements justify it.

## 4. Time and Reporting Semantics

- Store source timestamps as timezone-aware UTC values.
- Interpret reporting dates and render timestamps in `Asia/Bangkok`.
- Start and end dates are inclusive calendar dates in `Asia/Bangkok`.
- Posts, videos, and comments belong to a report when their creation timestamp falls inside the resolved UTC interval for those local dates.
- Page daily Insights use the metric date returned by Meta, normalized to the Page/report timezone.
- The default start date is one calendar month before the current local date; the default end date is the current local date.
- URLs must preserve `page_id`, `from`, `to`, and enabled chart metrics so a report view can be refreshed or shared after authentication.

## 5. Data Model

### `pages`

Stores the Facebook Page ID, display name, category, public link, timezone, enabled state, daily-sync setting, creation time, and latest successful/attempted synchronization timestamps. Disabling a Page is a soft delete and preserves all history.

### `admin_users`

Stores username, password hash, enabled state, optional future role, creation time, and last login time. Version 1 contains one account but must not hard-code credentials.

### `sync_jobs`

Stores Page, job type (`daily`, `manual`, or `backfill`), inclusive requested dates, status, progress counters, checkpoint/cursor, request count, retry time, error classification, error detail safe for display, initiator, and timestamps. Only one active synchronization job may exist per Page.

### `posts`

Stores Page and post identity, created time, message, normalized media type, permalink, attachment metadata needed by the report, current reaction breakdown, comment count, share count, and the latest capture time. Media types must cover at least `photo`, `album`, `link`, `video`, and `status/other`.

### `post_snapshots`

Stores the counters for a post at each successful capture time. Snapshots preserve changes in engagement and allow later trend features without changing the Version 1 KPI definition.

### `page_daily_insights`

Stores Page, metric date, metric name, numeric value, source period, Graph API version, and capture time. A metric-name/value design is required because Meta can rename or deprecate metrics. A uniqueness constraint prevents duplicate values for the same Page, date, metric, period, and source version.

### `videos`

Stores Page and video identity, created time, title, length, permalink, views, average watch time, complete views, capture time, and metric availability. Values that Meta does not return remain null rather than zero.

### `comments`

Stores Page, post, and comment identity, comment creation time, report-safe post excerpt, content, available author label, likes, replies, and capture time. Missing or hidden author names use the display label `(ẩn)`.

### `metric_availability`

Records Page, metric name, Graph API version, availability status, last successful observation, last check, and a sanitized reason. One unavailable Insights metric must not fail the remaining synchronization job.

### `audit_events`

Records administrator login events and state-changing actions such as Page creation, Page disablement, manual synchronization, backfill, and job cancellation. It must not contain the Page Access Token or raw secrets.

## 6. Graph API Collection

The worker queries the configured Graph API version and uses `FB_PAGE_ACCESS_TOKEN`. The initial field/metric registry targets:

- Page identity: name, category, followers/fan count when available, and public link.
- Posts: ID, created time, message, permalink, attachments/media type, shares, comments summary, total reactions, and reaction types Like, Love, Haha, Wow, Sad, Angry, and Care.
- Page daily Insights: new followers, total followers, post engagements, video views, and Page views where the active Graph API version supports them.
- Videos: title/description, created time, length, views, average watch time, complete views, and permalink where supported.
- Comments: creation time, content, available author label, likes, and replies.

The exact Graph API metric identifiers belong in a versioned registry, not scattered through report code. Each response is validated independently. Unsupported/deprecated metrics are marked unavailable, while supported metrics continue to load.

Pagination must continue until the requested interval is complete, Meta provides no next cursor, the job is cancelled, or a non-retryable error occurs. Checkpoints store the last safe cursor/date boundary. Retries use exponential backoff with jitter for timeouts, transient server errors, and rate limiting. Authentication/permission errors stop the affected job and display a sanitized actionable message.

## 7. KPI Definitions

For posts created inside the selected interval:

- **Posts:** count of posts.
- **Reactions:** sum of Like, Love, Haha, Wow, Sad, Angry, and Care.
- **Comments:** sum of post comment counts.
- **Shares:** sum of post share counts.
- **Total engagement:** reactions + comments + shares.
- **Average engagement per post:** total engagement divided by post count; zero when there are no posts.
- **Top five posts:** descending total engagement, then descending creation time, then stable post ID tie-breaker.
- **Format summary:** count, average engagement, total engagement, reactions, comments, and shares grouped by normalized media type.
- **Posting-time matrix:** count of posts grouped by local hour (00h–23h) and Vietnamese weekday (T2–CN).

For daily Page Insights:

- **Current followers:** the latest available follower value on or before the selected end date.
- **Follower growth:** current followers minus the latest available follower value before the selected start date.
- **Daily new followers:** the daily metric value returned by Meta, not a fabricated difference when that metric is absent.
- **Daily engagement, video views, and Page views:** values returned for each metric date.

Missing data is distinct from numeric zero. Charts must leave a gap for a missing observation. KPI cards and exports use `Không có dữ liệu` or blank cells where appropriate.

## 8. Dashboard

The visual direction is a dark analytics dashboard based on `Báo cáo FB thang-1.JPG`. The global report toolbar contains:

- Page selector.
- Start-date and end-date inputs.
- Apply action.
- Latest successful synchronization timestamp and data-warning indicator.
- Excel download action.

The primary dashboard contains:

- KPI cards for Posts, Total engagement, Current followers, Reactions, and Average engagement per post.
- Posts by day.
- Followers over time with follower growth in the selected interval.
- Engagement by day.
- Reaction types by day.
- Video views/viewers when supported.
- Top five posts by engagement, with post date, media type, score, and link to the original post.
- Optional drill-down tables for Posts, Videos, and Comments.

### Daily Insights chart

Add a full-width multi-line chart based on `Báo cáo FB thang-5.JPG`. It uses the active global Page and date filters and includes toggles for:

- New followers per day.
- Total followers.
- Post engagements.
- Video views.
- Page views.

The chart offers `Hiện tất cả` and `Chỉ metric nhỏ`. The latter uses a documented secondary-axis or normalized presentation so small series remain legible beside large spikes. Tooltips show local date, value, and unit. The legend toggles series and the selected series are preserved in the URL.

Below the chart, show totals for additive metrics in the selected interval and state how many metrics returned data. Non-additive total-followers is shown as the latest value, not summed. An unavailable metric has a disabled toggle and explanatory tooltip. Missing days are not converted to zero or connected across gaps.

## 9. Administration and Authentication

The administrator signs in through a dedicated page. The first account is created with a management command that accepts the username interactively or via a non-secret argument and reads the password interactively or from a deployment secret. Passwords use a modern adaptive password hash.

Authenticated sessions use secure, `HttpOnly`, `SameSite=Lax` cookies. Production requires HTTPS and the cookie `Secure` flag. State-changing requests require CSRF protection. Login attempts are rate-limited and audit logged without recording passwords.

The Page administration screen supports:

- Listing active and disabled Pages with last-sync health.
- Adding a Page ID and validating access before saving.
- Editing display metadata and daily-sync status.
- Disabling/re-enabling a Page without deleting history.
- Starting an immediate synchronization.
- Starting a default 90-day or custom-date backfill.
- Viewing progress and cancelling an active job.

The Page Access Token is never accepted by a browser form, stored in PostgreSQL, returned by an API, or printed in logs.

## 10. Excel Export

The export uses the selected Page and inclusive date interval. Its filename is `facebook-report_<page-id>_<from>_<to>.xlsx` with filesystem-unsafe characters removed.

It preserves the structure and presentation conventions of `Sample_Report.xlsx`:

1. **Tổng quan:** report title, export time, report period, Page, Page ID, latest followers, category, and link.
2. **Posts:** Created, Message, Media, Reactions, Like, Love, Haha, Wow, Sad, Angry, Care, Comments, Shares, Engagement, and Permalink.
3. **Insights:** Date and the configured Page daily Insights metrics.
4. **Videos:** Title, Created, Length (s), Views, Avg Watch Time, Complete Views, and Permalink.
5. **Định dạng:** format-level count and engagement summary.
6. **Giờ đăng:** 24-by-7 local posting-time matrix.
7. **Comments:** Thời gian, Bài viết, Nội dung comment, Người bình luận, Likes, and Replies.

The exporter applies styled headers, readable widths, appropriate date/number formats, and freeze panes modeled on the sample. It writes blanks for unavailable optional metrics. All formulas and totals must use the same reporting service as the dashboard.

## 11. Errors and Operational Behavior

- A failed or partial job does not delete previously successful data.
- A Page has at most one active synchronization job; duplicate requests return the existing job state.
- Job progress exposes date/cursor progress, fetched object counts, request count, retry state, and sanitized errors.
- The dashboard clearly distinguishes fresh, stale, partial, and unavailable data.
- Job cancellation occurs at safe checkpoint boundaries.
- Database migrations run explicitly during deployment, not concurrently from every process.
- Services expose health/readiness endpoints.
- PostgreSQL data is stored in a persistent volume and has a documented backup/restore procedure.
- Logs are structured and redact access tokens, session material, passwords, and Graph API URLs containing secrets.

## 12. Testing and Acceptance

### Unit tests

- Inclusive date-to-UTC interval conversion across the `Asia/Bangkok` boundary.
- KPI arithmetic, zero-post behavior, tie-breaking, format grouping, and posting-time matrix.
- Missing metric behavior and additive versus non-additive Insights summaries.
- Graph response normalization and metric-registry behavior.

### Integration tests

- PostgreSQL constraints, migrations, Page soft deletion, and one-active-job enforcement.
- Sync pagination, checkpoint resume, retry, cancellation, and partial metric success using mocked Graph API responses.
- Authentication, cookie settings, CSRF protection, login throttling, and audit events.
- Report query parity between API JSON and Excel source rows.

### Workbook tests

- Exactly seven named sheets in the approved order.
- Required columns, representative formatting, freeze panes, and date/number formats.
- Totals in Posts, format summary, posting-time matrix, and dashboard API agree for the same fixture.
- Blank optional metric cells remain blank rather than becoming zero.

### End-to-end tests

- Sign in with the single administrator account.
- Add and validate a Page, trigger the 90-day backfill, and observe progress.
- Select a Page and custom dates; refresh and retain the selection through the URL.
- Toggle daily Insights series and retain the series selection.
- Download and open the Excel report for the selected Page and dates.

Version 1 is accepted when the default Page can be registered, its available data can be synchronized without exposing the token, the approved dashboard views load from PostgreSQL for the default one-month period, and the downloaded workbook matches the seven-sheet report contract.

# Facebook Reporting Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an authenticated multi-Page Facebook reporting platform that synchronizes Graph API data into PostgreSQL, renders a date-filtered dashboard, and exports the approved seven-sheet workbook.

**Architecture:** FastAPI owns authentication, Page administration, report queries, and Excel downloads. A separate Python worker polls PostgreSQL-backed jobs for daily/manual/backfill collection. A React/TypeScript frontend consumes FastAPI only; dashboard and Excel share one reporting service.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16, httpx, Argon2, openpyxl, pytest, React, TypeScript, Vite, TanStack Query, Recharts, Vitest, Playwright, Docker Compose.

## Global Constraints

- Default Page ID: `1125132200689307`.
- Read the shared token only from `FB_PAGE_ACCESS_TOKEN`; never persist, return, or log it.
- Reporting timezone: `Asia/Bangkok`; both selected dates are inclusive.
- Default period: one calendar month before today through today.
- Version 1 has one administrator; preserve a future `role` field.
- A Page can have only one active synchronization job.
- Missing metrics remain null; never fabricate zero.
- Excel order: `Tổng quan`, `Posts`, `Insights`, `Videos`, `Định dạng`, `Giờ đăng`, `Comments`.
- Keep existing `fbcrawl.py` behavior and tests passing.

## File Map

```text
backend/app/{main,config,db,models,schemas,auth,dependencies,cli}.py
backend/app/graph/{client,metrics}.py
backend/app/sync/{jobs,service}.py
backend/app/reporting/{dates,service,excel}.py
backend/app/routers/{auth,pages,jobs,reports}.py
backend/app/worker.py
backend/alembic/versions/0001_initial.py
backend/tests/test_*.py
frontend/src/api/{client,types}.ts
frontend/src/auth/AuthProvider.tsx
frontend/src/components/{AppShell,DateRangeFilter,KpiCards,DailyInsightsChart}.tsx
frontend/src/pages/{LoginPage,DashboardPage,PagesAdminPage,JobsPage}.tsx
frontend/tests/*.test.tsx
frontend/e2e/reporting.spec.ts
compose.yaml
```

---

### Task 1: Backend Skeleton and Configuration

**Files:** Create `backend/pyproject.toml`, `backend/app/config.py`, `backend/app/db.py`, `backend/app/main.py`, `backend/tests/conftest.py`, `backend/tests/test_health.py`.

**Interfaces:** `Settings`, `get_settings()`, `get_session()`, `create_app() -> FastAPI`.

- [ ] **Step 1: Write failing tests**

```python
def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}

def test_token_is_not_in_openapi(client):
    assert "test-page-token" not in client.get("/openapi.json").text
```

- [ ] **Step 2: Verify failure**

Run: `cd backend && python -m pytest tests/test_health.py -q`
Expected: FAIL because `app.main` is absent.

- [ ] **Step 3: Implement minimal app**

```python
class Settings(BaseSettings):
    database_url: str
    fb_page_access_token: str
    fb_graph_version: str = "v25.0"
    app_secret_key: str
    report_timezone: str = "Asia/Bangkok"
    default_page_id: str = "1125132200689307"
```

Create a SQLAlchemy session factory with `pool_pre_ping=True`; add `GET /api/health`; list exact runtime and test dependencies in `pyproject.toml`.

- [ ] **Step 4: Verify passing state**

Run: `cd backend && python -m pytest tests/test_health.py -q && python -m compileall app tests`
Expected: 2 tests pass and compile exits 0.

- [ ] **Step 5: Commit**

```powershell
git add backend
git commit -m "feat: scaffold reporting API"
```

---

### Task 2: Database Schema and Migration

**Files:** Create `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_initial.py`, `backend/app/models.py`, `backend/tests/test_models.py`.

**Interfaces:** Models `Page`, `AdminUser`, `AdminSession`, `SyncJob`, `Post`, `PostSnapshot`, `PageDailyInsight`, `Video`, `Comment`, `MetricAvailability`, `AuditEvent`; enums `JobType`, `JobStatus`, `MetricStatus`.

- [ ] **Step 1: Write failing uniqueness/nullability tests**

```python
def test_daily_metric_unique(db_session, insight_factory):
    db_session.add(insight_factory(metric="page_follows", value=10))
    db_session.commit()
    db_session.add(insight_factory(metric="page_follows", value=11))
    with pytest.raises(IntegrityError):
        db_session.commit()

def test_unavailable_video_metric_stays_null(video_factory):
    assert video_factory(views=None).views is None
```

- [ ] **Step 2: Run test; expect missing models**

Run: `cd backend && python -m pytest tests/test_models.py -q`.

- [ ] **Step 3: Implement models and migration**

Use UTC-aware timestamps, integer internal keys, unique external IDs, and indexes on `(page_id, created_at)`. Add PostgreSQL partial unique index:

```sql
CREATE UNIQUE INDEX uq_active_job_per_page ON sync_jobs(page_id)
WHERE status IN ('queued','running','retrying','cancelling');
```

Store only SHA-256 hashes of random session/CSRF values. Add unique daily metric key `(page_id, metric_date, metric_name, period, source_version)`.

- [ ] **Step 4: Verify migration and tests**

Run: `cd backend && alembic upgrade head && python -m pytest tests/test_models.py -q`
Expected: migration and all model tests pass.

- [ ] **Step 5: Commit:** `git commit -am "feat: add reporting database schema"` after staging new migration/model/test files.

---

### Task 3: Administrator Authentication

**Files:** Create `backend/app/auth.py`, `backend/app/dependencies.py`, `backend/app/routers/auth.py`, `backend/app/cli.py`, `backend/tests/test_auth.py`; modify `main.py` and `schemas.py`.

**Interfaces:** `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`; CLI `python -m app.cli create-admin --username admin`.

- [ ] **Step 1: Write failing login, cookie, CSRF, throttle, and logout tests**

```python
def test_login_cookie(client, admin_user):
    response = client.post("/api/auth/login", json={"username":"admin","password":"correct horse battery staple"})
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert response.json()["csrf_token"]

def test_logout_requires_csrf(auth_client):
    assert auth_client.post("/api/auth/logout").status_code == 403
```

- [ ] **Step 2:** Run `cd backend && python -m pytest tests/test_auth.py -q`; expect route failures.

- [ ] **Step 3: Implement authentication**

Use Argon2, `secrets.token_urlsafe(32)`, hashed opaque sessions, constant-time comparison, `HttpOnly`/`SameSite=Lax` cookie, production `Secure`, and `X-CSRF-Token` for mutations. Limit failures to 5 per username+IP per 15 minutes. CLI prompts twice with `getpass`, requires 12 characters, and refuses overwrite.

- [ ] **Step 4:** Rerun auth tests; expect all pass.

- [ ] **Step 5: Commit:** `git commit -m "feat: add administrator authentication"`.

---

### Task 4: Graph API Boundary and Metric Registry

**Files:** Create `backend/app/graph/client.py`, `backend/app/graph/metrics.py`, `backend/tests/test_graph_client.py`.

**Interfaces:** `GraphClient.get_page_identity()`, `iter_posts()`, `iter_insights()`, `iter_videos()`, `iter_comments()`; `MetricDefinition`.

- [ ] **Step 1: Write failing pagination/redaction tests**

```python
def test_posts_follow_next(graph_client, two_page_graph):
    assert [p["id"] for p in graph_client.iter_posts("PAGE", START, END)] == ["1", "2"]

def test_error_redacts_token(graph_client, bad_graph):
    with pytest.raises(GraphAPIError) as exc:
        graph_client.get_page_identity("PAGE")
    assert "SECRET" not in str(exc.value)
```

- [ ] **Step 2:** Run `cd backend && python -m pytest tests/test_graph_client.py -q`; expect import failure.

- [ ] **Step 3: Implement client and logical registry**

```python
METRICS = {
 "daily_new_followers": MetricDefinition(("page_daily_follows_unique","page_daily_follows"), "day", True, "people"),
 "followers_total": MetricDefinition(("page_follows",), "day", False, "people"),
 "post_engagements": MetricDefinition(("page_post_engagements",), "day", True, "interactions"),
 "video_views": MetricDefinition(("page_video_views",), "day", True, "views"),
 "page_views": MetricDefinition(("page_views_total",), "day", True, "views"),
}
```

Classify errors as authentication, permission, rate-limit, transient, or invalid request. Do not substitute metrics with different semantics.

- [ ] **Step 4:** Rerun tests; verify pagination, timeout, fallback, and redaction pass.

- [ ] **Step 5: Commit:** `git commit -m "feat: add Facebook Graph API client"`.

---

### Task 5: Page Administration and Job State Machine

**Files:** Create `backend/app/routers/pages.py`, `backend/app/routers/jobs.py`, `backend/app/sync/jobs.py`, `backend/tests/test_pages_api.py`, `backend/tests/test_jobs.py`.

**Interfaces:** Page list/create/update, `POST /pages/{id}/sync`, `POST /pages/{id}/backfill`, job list/detail/cancel; `enqueue_job()` and `claim_next_job()`.

- [ ] **Step 1: Write failing API/state tests**

```python
def test_new_page_gets_90_inclusive_days(auth_client, freezer):
    freezer.move_to("2026-07-12")
    body = auth_client.post("/api/pages", headers=csrf(), json={"page_id":"1125132200689307"}).json()
    assert (body["initial_job"]["start_date"], body["initial_job"]["end_date"]) == ("2026-04-14","2026-07-12")

def test_duplicate_active_job_returns_409(auth_client, running_job):
    assert auth_client.post(f"/api/pages/{running_job.page_id}/sync", headers=csrf()).status_code == 409
```

- [ ] **Step 2:** Run focused tests; expect missing routes.

- [ ] **Step 3: Implement contracts**

Validate Page access through `get_page_identity` before persistence. Omitted dates mean today minus 89 days through today. Soft-disable only. Record every mutation in `AuditEvent`. Claim jobs with `FOR UPDATE SKIP LOCKED`; duplicate active requests return existing job ID. Cancellation moves to `cancelling` until a safe checkpoint.

- [ ] **Step 4:** Run Page/job tests; cover access failure, custom range, soft disable, conflict, claim locking, progress, cancellation.

- [ ] **Step 5: Commit:** `git commit -m "feat: add page and job administration"`.

---

### Task 6: Idempotent Synchronization Worker

**Files:** Create `backend/app/sync/service.py`, `backend/app/worker.py`, `backend/tests/test_sync.py`; modify `sync/jobs.py`.

**Interfaces:** `SyncService.run(job_id, progress)`, normalization functions, `run_worker(worker_id, poll_seconds=2)`.

- [ ] **Step 1: Write failing idempotency/partial-success tests**

```python
def test_repeat_sync_upserts_and_snapshots(sync_service, repeated_jobs, db):
    for job in repeated_jobs: sync_service.run(job.id, lambda _: None)
    assert count(db, Post) == 1
    assert count(db, PostSnapshot) == 2

def test_bad_insight_does_not_discard_posts(sync_service, partial_graph, job, db):
    sync_service.run(job.id, lambda _: None)
    assert count(db, Post) > 0
    assert metric_status(db, "page_views") == "unavailable"
```

- [ ] **Step 2:** Run sync tests; expect missing service.

- [ ] **Step 3: Implement worker**

Normalize timestamps to UTC, media to photo/album/link/video/status-other, reactions to explicit fields, and hidden authors to `(ẩn)`. Upsert current rows, append post snapshots, commit batches of 100 with checkpoint in the same transaction. Retry transient/rate-limit failures with exponential backoff+jitter; fail auth/permission errors. Recover expired worker leases. At 02:00 Asia/Bangkok enqueue yesterday-through-today for eligible Pages.

- [ ] **Step 4:** Verify idempotency, checkpoint resume, retry, cancellation, lease recovery, partial metric success, and daily scheduling.

- [ ] **Step 5: Commit:** `git commit -m "feat: synchronize Facebook reporting data"`.

---

### Task 7: Shared Reporting Dataset and API

**Files:** Create `backend/app/reporting/dates.py`, `backend/app/reporting/service.py`, `backend/app/routers/reports.py`, `backend/tests/test_dates.py`, `backend/tests/test_reporting.py`, `backend/tests/test_reports_api.py`.

**Interfaces:** `resolve_report_range() -> UtcInterval`, `ReportingService.build() -> ReportDataset`, `GET /api/reports/{page_id}`.

- [ ] **Step 1: Write failing date/KPI tests**

```python
def test_bangkok_inclusive_dates():
    value = resolve_report_range(date(2026,7,1), date(2026,7,2), "Asia/Bangkok")
    assert value.start_utc.isoformat() == "2026-06-30T17:00:00+00:00"
    assert value.end_exclusive_utc.isoformat() == "2026-07-02T17:00:00+00:00"

def test_engagement(report):
    assert report.summary.total_engagement == report.summary.reactions + report.summary.comments + report.summary.shares
```

- [ ] **Step 2:** Run focused tests; expect missing reporting modules.

- [ ] **Step 3: Implement dataset**

Define typed summary, daily posts, daily Insights, top posts, format summary, 24x7 matrix, and detail rows. Top-post order: engagement desc, creation desc, external ID asc. Followers use latest on/before end; growth subtracts latest strictly before start. Additive totals expose available/expected days; total followers is latest, never sum. Include latest sync, active job, and fresh/stale/partial/unavailable state. Default dates use `relativedelta(months=1)`.

- [ ] **Step 4:** Run reporting/API tests; verify formulas, null gaps, grouping, matrix, defaults, and authorization.

- [ ] **Step 5: Commit:** `git commit -m "feat: add shared reporting service"`.

---

### Task 8: Seven-Sheet Excel Export

**Files:** Create `backend/app/reporting/excel.py`, `backend/tests/test_excel.py`; modify reports router.

**Interfaces:** `build_workbook(dataset, exported_at) -> Workbook`; `GET /api/reports/{page_id}/excel`.

- [ ] **Step 1: Write failing workbook contract**

```python
def test_workbook_contract(dataset):
    wb = build_workbook(dataset, EXPORTED_AT)
    assert wb.sheetnames == ["Tổng quan","Posts","Insights","Videos","Định dạng","Giờ đăng","Comments"]
    assert [c.value for c in wb["Posts"][1]] == ["Created","Message","Media","Reactions","Like","Love","Haha","Wow","Sad","Angry","Care","Comments","Shares","Engagement","Permalink"]
    assert wb["Videos"]["E2"].value is None
```

- [ ] **Step 2:** Run Excel tests; expect missing exporter.

- [ ] **Step 3: Implement exporter**

Consume `ReportDataset` only; do not recalculate KPIs. Match sample headers, widths, formats, freeze panes, and sheet order. Write true Excel dates and blanks for nulls. Stream MIME `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` with `facebook-report_<page-id>_<from>_<to>.xlsx`.

- [ ] **Step 4:** Verify sheets, styles, blanks, KPI parity, and Content-Disposition.

- [ ] **Step 5: Commit:** `git commit -m "feat: export seven-sheet Facebook reports"`.

---

### Task 9: React Authentication and Administration

**Files:** Create frontend Vite project, API client/types, `AuthProvider`, `AppShell`, `LoginPage`, `PagesAdminPage`, `JobsPage`, router, styles, and corresponding Vitest tests.

**Interfaces:** `/login`, `/dashboard`, `/admin/pages`, `/admin/jobs`; browser requests use `credentials: "include"` and CSRF header on mutations.

- [ ] **Step 1: Write failing login/Page tests**

```tsx
it("logs in", async () => {
  renderApp("/login");
  await user.type(screen.getByLabelText("Tên đăng nhập"), "admin");
  await user.type(screen.getByLabelText("Mật khẩu"), "correct horse battery staple");
  await user.click(screen.getByRole("button", {name:"Đăng nhập"}));
  expect(await screen.findByText("Tổng quan Facebook")).toBeVisible();
});
```

- [ ] **Step 2:** Run `cd frontend && npm test -- --run`; expect missing components.

- [ ] **Step 3: Implement UI**

Use React Router and TanStack Query. Call `/auth/me` on startup; keep CSRF in memory, never localStorage. Page cards show ID, status, latest sync, active job, and edit/disable/sync/backfill actions. Poll active jobs only until terminal state. Use accessible Vietnamese labels, focus, loading, empty, and error states.

- [ ] **Step 4:** Verify login, logout, create, custom backfill, soft disable, sync conflict, and job progress tests.

- [ ] **Step 5: Commit:** `git commit -m "feat: add reporting web administration"`.

---

### Task 10: Dashboard and Daily Insights Chart

**Files:** Create `DateRangeFilter.tsx`, `KpiCards.tsx`, `DailyInsightsChart.tsx`, `DashboardPage.tsx`, dashboard tests, and Playwright report flow.

**Interfaces:** URL parameters `page_id`, `from`, `to`, `metrics`; chart consumes daily series and availability metadata.

- [ ] **Step 1: Write failing filter/missing-data tests**

```tsx
it("defaults to one calendar month", async () => {
  vi.setSystemTime(new Date("2026-07-12T03:00:00Z"));
  renderDashboard("?page_id=1");
  expect(await screen.findByLabelText("Từ ngày")).toHaveValue("2026-06-12");
  expect(screen.getByLabelText("Đến ngày")).toHaveValue("2026-07-12");
});

it("disables unavailable page views", () => {
  renderInsights({page_views:{status:"unavailable",values:[null]}});
  expect(screen.getByRole("button", {name:/Lượt xem trang/})).toBeDisabled();
});
```

- [ ] **Step 2:** Run dashboard test; expect missing components.

- [ ] **Step 3: Implement approved dark dashboard**

Add five KPI cards, daily posts, followers, engagement, reaction stack, video panel, top five posts, and full-width daily Insights chart. Toggles: new followers, total followers, post engagements, video views, Page views. `Hiện tất cả` enables available metrics. `Chỉ metric nhỏ` places series below 10% of the largest maximum on a labeled right axis. Use raw tooltip values, `connectNulls={false}`, Vietnamese number/date formats, and accessible text/table fallback. Preserve filters/toggles in URL. Excel link uses active filters.

- [ ] **Step 4:** Run `npm test -- --run` and Playwright login → filter → toggle → Excel test; expect pass.

- [ ] **Step 5: Commit:** `git commit -m "feat: add Facebook analytics dashboard"`.

---

### Task 11: Containers, Operations, and Full Verification

**Files:** Create backend/frontend Dockerfiles, `compose.yaml`, `.env.example`; modify `.gitignore`, `README.md`, and CLI.

**Interfaces:** Services `db`, `api`, `worker`, `frontend`; CLI `create-admin`, `seed-default-page`.

- [ ] **Step 1: Add executable smoke workflow to README**

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose exec api alembic upgrade head
docker compose exec api python -m app.cli create-admin --username admin
docker compose exec api python -m app.cli seed-default-page
Invoke-RestMethod http://localhost:8000/api/health
```

- [ ] **Step 2: Implement deployment**

Use PostgreSQL 16 named volume and health check; run migrations explicitly; start API and worker separately; serve frontend via nginx and proxy `/api`. Ignore `.superpowers/`, generated `.xlsx`, builds, DB data, and secrets. Keep the user's untracked `Sample_Report.xlsx` untouched.

- [ ] **Step 3: Document operations**

Document variables, token rotation, daily 02:00 schedule, one-job rule, stale/partial states, `pg_dump`/`pg_restore`, metric deprecation troubleshooting, and future multi-user roles.

- [ ] **Step 4: Run complete verification**

```powershell
cd backend; python -m pytest -q --cov=app --cov-report=term-missing
cd ..\frontend; npm run lint; npm test -- --run; npm run build
cd ..; docker compose config; docker compose up -d --build
docker compose exec api alembic upgrade head
cd frontend; npx playwright test
cd ..; python -m unittest discover -s tests -v
git diff --check
```

Expected: every command exits 0; services are healthy; existing crawler tests still pass; no secret appears in committed files.

- [ ] **Step 5: Commit:** `git commit -m "chore: package Facebook reporting platform"`.

## Review Gates

Execute tasks in order. Review and run focused tests after every commit. After Tasks 6, 8, and 10, rerun all earlier backend/frontend tests because these are integration boundaries. Do not run a real 90-day Page backfill until mock Graph contracts, token redaction, and active-job locking pass. First smoke-test the default Page over one day, inspect request counts and metric availability, then expand the range.

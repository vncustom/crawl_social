import { expect, test } from "@playwright/test";

const report = {
  page_id: 1,
  external_page_id: "1125132200689307",
  page_name: "HTV3",
  start_date: "2026-06-13",
  end_date: "2026-07-13",
  summary: {
    posts: 105,
    reactions: 7476,
    comments: 900,
    shares: 723,
    total_engagement: 9099,
    average_engagement: 86.7,
    current_followers: 20768,
    follower_growth: 2374,
  },
  daily_posts: [{ metric_date: "2026-07-12", posts: 4, reactions: 100, comments: 20, shares: 10, engagement: 130 }],
  daily_insights: [{ metric_date: "2026-07-12", daily_new_followers: 12, followers_total: 20768, post_engagements: 130, video_views: 400, page_views: 50 }],
  top_posts: [{ external_post_id: "p1", created: "2026-07-12T10:00:00Z", message: "Bài viết nổi bật", media: "photo", reactions: 100, like: 90, love: 10, haha: 0, wow: 0, sad: 0, angry: 0, care: 0, comments: 20, shares: 10, engagement: 130, permalink: "https://facebook.com/p1" }],
  formats: [],
  posting_hours: [],
  videos: [],
  comments_detail: [],
  latest_sync_at: "2026-07-13T02:00:00Z",
  active_job_id: null,
};

test("login, filter, toggle an insight and download Excel", async ({ page }) => {
  let authenticated = false;
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (!url.pathname.startsWith("/api/")) {
      await route.continue();
      return;
    }
    if (url.pathname === "/api/auth/me") {
      await route.fulfill(authenticated
        ? { json: { username: "admin", role: "admin" } }
        : { status: 401, json: { detail: "Unauthorized" } });
    } else if (url.pathname === "/api/auth/login") {
      authenticated = true;
      await route.fulfill({ json: { username: "admin", role: "admin", csrf_token: "csrf" } });
    } else if (url.pathname === "/api/pages") {
      await route.fulfill({ json: [{ id: 1, page_id: "1125132200689307", display_name: "HTV3", enabled: true, daily_sync_enabled: true }] });
    } else if (url.pathname === "/api/reports/1/excel") {
      await route.fulfill({
        status: 200,
        headers: {
          "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          "Content-Disposition": "attachment; filename=facebook-report.xlsx",
        },
        body: "mock workbook",
      });
    } else if (url.pathname === "/api/reports/1") {
      await route.fulfill({ json: report });
    } else {
      await route.fulfill({ status: 404, json: {} });
    }
  });

  await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Đăng nhập quản trị" })).toBeVisible();
  await page.getByLabel("Tên đăng nhập").fill("admin");
  await page.getByLabel("Mật khẩu").fill("correct horse battery staple");
  await page.getByRole("button", { name: "Đăng nhập" }).click();

  await expect(page.getByRole("heading", { name: "Tổng quan Facebook" })).toBeVisible();
  await page.getByLabel("Từ ngày").fill("2026-07-01");
  await expect(page).toHaveURL(/from=2026-07-01/);

  const engagementToggle = page.getByRole("button", { name: "Tương tác bài" });
  await expect(engagementToggle).toHaveAttribute("aria-pressed", "true");
  await engagementToggle.click();
  await expect(engagementToggle).toHaveAttribute("aria-pressed", "false");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: /Tải Excel/ }).click();
  expect((await downloadPromise).suggestedFilename()).toBe("facebook-report.xlsx");
});

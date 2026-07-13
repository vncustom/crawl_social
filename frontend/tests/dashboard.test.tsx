import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { AppRouter } from "../src/router";


const report = {
  page_id: 1, external_page_id: "1125132200689307", page_name: "HTV", start_date: "2026-06-13", end_date: "2026-07-13",
  summary: { posts: 105, reactions: 7476, comments: 900, shares: 723, total_engagement: 9099, average_engagement: 86.7, current_followers: 20768, follower_growth: 2374 },
  daily_posts: [{ metric_date: "2026-07-12", posts: 4, reactions: 100, comments: 20, shares: 10, engagement: 130 }],
  daily_insights: [{ metric_date: "2026-07-12", daily_new_followers: 12, followers_total: 20768, post_engagements: 130, video_views: 400, page_views: null }],
  top_posts: [{ external_post_id: "p1", created: "2026-07-12T10:00:00Z", message: "Bài viết nổi bật", media: "photo", reactions: 100, like: 90, love: 10, haha: 0, wow: 0, sad: 0, angry: 0, care: 0, comments: 20, shares: 10, engagement: 130, permalink: "https://facebook.com/p1" }],
  formats: [], posting_hours: [], videos: [], comments_detail: [], latest_sync_at: "2026-07-13T02:00:00Z", active_job_id: null,
};

beforeEach(() => {
  vi.setSystemTime(new Date("2026-07-13T03:00:00Z"));
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/api/auth/me")) return Response.json({ username: "admin", role: "admin" });
    if (url.endsWith("/api/pages")) return Response.json([{ id: 1, page_id: "1125132200689307", display_name: "HTV", enabled: true, daily_sync_enabled: true }]);
    if (url.includes("/api/reports/1?")) return Response.json(report);
    return new Response("{}", { status: 404 });
  }));
});

it("defaults to one calendar month and renders KPIs", async () => {
  render(<AppRouter initialEntries={["/dashboard?page_id=1"]} />);

  expect(await screen.findByLabelText("Từ ngày")).toHaveValue("2026-06-13");
  expect(screen.getByLabelText("Đến ngày")).toHaveValue("2026-07-13");
  expect(await screen.findByText("9.099")).toBeVisible();
  expect(screen.getByText("Bài viết nổi bật")).toBeVisible();
});

it("disables an insight metric when every value is missing", async () => {
  render(<AppRouter initialEntries={["/dashboard?page_id=1"]} />);

  expect(await screen.findByRole("button", { name: /Lượt xem trang/ })).toBeDisabled();
  expect(screen.queryByText("0 lượt xem trang")).not.toBeInTheDocument();
});

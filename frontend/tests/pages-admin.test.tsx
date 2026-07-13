import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { AppRouter } from "../src/router";


it("creates a page with the default backfill", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/api/auth/me")) return Response.json({ username: "admin", role: "admin" });
    if (url.endsWith("/api/pages") && init?.method === "POST") return Response.json({ id: 1, page_id: "1125132200689307", display_name: "HTV", enabled: true, daily_sync_enabled: true, initial_job: { id: 1, status: "queued", start_date: "2026-04-15", end_date: "2026-07-13" } }, { status: 201 });
    if (url.endsWith("/api/pages")) return Response.json([]);
    return new Response("{}", { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<AppRouter initialEntries={["/admin/pages"]} initialCsrfToken="csrf" />);

  await userEvent.click(await screen.findByRole("button", { name: "Thêm Page" }));
  await userEvent.type(screen.getByLabelText("Facebook Page ID"), "1125132200689307");
  await userEvent.click(screen.getByRole("button", { name: "Kiểm tra và lưu" }));

  expect(await screen.findByText("Đang chờ backfill")).toBeVisible();
  const createCall = fetchMock.mock.calls.find(([url, init]) => String(url).endsWith("/api/pages") && init?.method === "POST");
  expect(createCall).toBeDefined();
  expect(new Headers(createCall?.[1]?.headers).get("X-CSRF-Token")).toBe("csrf");
});

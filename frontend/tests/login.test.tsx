import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { AppRouter } from "../src/router";


it("redirects an unauthenticated visitor to login", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 401 })));

  render(<AppRouter initialEntries={["/dashboard"]} />);

  expect(await screen.findByRole("heading", { name: "Đăng nhập quản trị" })).toBeVisible();
  expect(screen.queryByText("Facebook Reports")).not.toBeInTheDocument();
});


it("logs in and opens the dashboard", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/api/auth/me")) return new Response("{}", { status: 401 });
    if (url.endsWith("/api/auth/login")) return Response.json({ username: "admin", role: "admin", csrf_token: "csrf" });
    if (url.endsWith("/api/pages")) return Response.json([]);
    return new Response("{}", { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<AppRouter initialEntries={["/login"]} />);

  await userEvent.type(screen.getByLabelText("Tên đăng nhập"), "admin");
  await userEvent.type(screen.getByLabelText("Mật khẩu"), "correct horse battery staple");
  await userEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));

  expect(await screen.findByText("Tổng quan Facebook")).toBeVisible();
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/auth/login",
    expect.objectContaining({ credentials: "include", method: "POST" }),
  );
});

import type { Admin, FacebookPage } from "./types";

let csrfToken = "";
export function setCsrfToken(value: string) { csrfToken = value; }

async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  if (init.method && init.method !== "GET" && csrfToken) headers.set("X-CSRF-Token", csrfToken);
  const response = await fetch(url, { ...init, headers, credentials: "include" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Không thể kết nối máy chủ." }));
    throw new Error(typeof body.detail === "string" ? body.detail : body.detail?.message || "Yêu cầu thất bại.");
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  me: () => request<Admin>("/api/auth/me"),
  login: async (username: string, password: string) => {
    const result = await request<Admin & { csrf_token: string }>("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
    setCsrfToken(result.csrf_token);
    return result;
  },
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),
  pages: () => request<FacebookPage[]>("/api/pages"),
  createPage: (pageId: string) => request<FacebookPage>("/api/pages", { method: "POST", body: JSON.stringify({ page_id: pageId }) }),
};

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setCsrfToken } from "../api/client";
import type { Admin } from "../api/types";
import { AuthContext, type AuthContextValue } from "./auth-context";

export function AuthProvider({ children, initialCsrfToken = "" }: { children: ReactNode; initialCsrfToken?: string }) {
  const [admin, setAdmin] = useState<Admin | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    setCsrfToken(initialCsrfToken);
    api.me().then(setAdmin).catch(() => setAdmin(null)).finally(() => setLoading(false));
  }, [initialCsrfToken]);
  const value = useMemo<AuthContextValue>(() => ({
    admin, loading,
    login: async (username, password) => { const result = await api.login(username, password); setAdmin(result); },
    logout: async () => { await api.logout(); setAdmin(null); },
  }), [admin, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, MemoryRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthProvider";
import { AppShell } from "./components/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { JobsPage } from "./pages/JobsPage";
import { LoginPage } from "./pages/LoginPage";
import { PagesAdminPage } from "./pages/PagesAdminPage";

export function AppRouter({initialEntries,initialCsrfToken}:{initialEntries?:string[];initialCsrfToken?:string}){
  const queryClient=new QueryClient({defaultOptions:{queries:{retry:false}}});
  const Router=initialEntries?MemoryRouter:BrowserRouter;
  const routerProps=initialEntries?{initialEntries}:{};
  return <QueryClientProvider client={queryClient}><AuthProvider initialCsrfToken={initialCsrfToken}><Router {...routerProps}><Routes><Route path="/login" element={<LoginPage/>}/><Route element={<AppShell/>}><Route path="/dashboard" element={<DashboardPage/>}/><Route path="/admin/pages" element={<PagesAdminPage/>}/><Route path="/admin/jobs" element={<JobsPage/>}/></Route><Route path="*" element={<Navigate to="/dashboard" replace/>}/></Routes></Router></AuthProvider></QueryClientProvider>;
}

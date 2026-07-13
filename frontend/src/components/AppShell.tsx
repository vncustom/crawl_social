import { BarChart3, Database, LogOut } from "lucide-react";
import { Navigate, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";

export function AppShell() {
  const auth = useAuth(); const navigate = useNavigate();
  if (auth.loading) return <div className="notice">Đang kiểm tra đăng nhập…</div>;
  if (!auth.admin) return <Navigate to="/login" replace />;
  return <div className="app-shell">
    <aside><div className="brand"><BarChart3/> Facebook Reports</div><nav><NavLink to="/dashboard"><BarChart3/> Dashboard</NavLink><NavLink to="/admin/pages"><Database/> Quản lý Page</NavLink></nav><button className="ghost" onClick={async()=>{await auth.logout();navigate("/login")}}><LogOut/> Đăng xuất</button></aside>
    <main><Outlet/></main>
  </div>;
}

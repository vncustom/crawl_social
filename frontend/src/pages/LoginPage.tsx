import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";

export function LoginPage() {
  const auth = useAuth(); const navigate = useNavigate();
  const [username,setUsername]=useState(""); const [password,setPassword]=useState(""); const [error,setError]=useState("");
  async function submit(event: FormEvent){event.preventDefault();setError("");try{await auth.login(username,password);navigate("/dashboard")}catch(err){setError(err instanceof Error?err.message:"Đăng nhập thất bại.")}}
  return <div className="login-page"><form className="login-card" onSubmit={submit}><p className="eyebrow">FACEBOOK ANALYTICS</p><h1>Đăng nhập quản trị</h1><p className="muted">Theo dõi hiệu quả nội dung từ một nơi duy nhất.</p><label>Tên đăng nhập<input value={username} onChange={e=>setUsername(e.target.value)} autoComplete="username"/></label><label>Mật khẩu<input type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete="current-password"/></label>{error&&<p role="alert" className="error">{error}</p>}<button type="submit">Đăng nhập</button></form></div>;
}

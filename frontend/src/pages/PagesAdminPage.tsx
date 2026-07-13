import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, RefreshCw } from "lucide-react";
import { api } from "../api/client";

export function PagesAdminPage(){
  const queryClient=useQueryClient(); const {data:pages=[]}=useQuery({queryKey:["pages"],queryFn:api.pages});
  const [open,setOpen]=useState(false); const [pageId,setPageId]=useState(""); const [created,setCreated]=useState(false);
  const create=useMutation({mutationFn:()=>api.createPage(pageId),onSuccess:async()=>{setCreated(true);setOpen(false);await queryClient.invalidateQueries({queryKey:["pages"]})}});
  return <section><header className="page-header"><div><p className="eyebrow">CẤU HÌNH</p><h1>Quản lý Facebook Page</h1><p className="muted">Thêm Page ID, theo dõi trạng thái đồng bộ và backfill dữ liệu.</p></div><button onClick={()=>setOpen(true)}><Plus/> Thêm Page</button></header>{created&&<div className="notice">Đang chờ backfill</div>}<div className="page-grid">{pages.map(page=><article className="page-card" key={page.id}><div><span className={page.enabled?"status active":"status"}>{page.enabled?"Đang hoạt động":"Đã tắt"}</span><h2>{page.display_name}</h2><code>{page.page_id}</code></div><button className="ghost"><RefreshCw/> Đồng bộ ngay</button></article>)}</div>{open&&<div className="modal-backdrop"><form className="modal" onSubmit={e=>{e.preventDefault();create.mutate()}}><h2>Thêm Facebook Page</h2><label>Facebook Page ID<input value={pageId} onChange={e=>setPageId(e.target.value)} pattern="[0-9]+" required/></label><p className="muted">Hệ thống sẽ kiểm tra quyền truy cập và backfill 90 ngày gần nhất.</p><div className="actions"><button type="button" className="ghost" onClick={()=>setOpen(false)}>Hủy</button><button type="submit" disabled={create.isPending}>Kiểm tra và lưu</button></div></form></div>}</section>;
}

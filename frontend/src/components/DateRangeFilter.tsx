import type { FacebookPage } from "../api/types";

export function DateRangeFilter({pages,pageId,from,to,onChange}:{pages:FacebookPage[];pageId:string;from:string;to:string;onChange:(value:{pageId:string;from:string;to:string})=>void}){
  return <div className="filters"><label>Page<select value={pageId} onChange={e=>onChange({pageId:e.target.value,from,to})}>{pages.map(p=><option key={p.id} value={p.id}>{p.display_name}</option>)}</select></label><label>Từ ngày<input type="date" value={from} onChange={e=>onChange({pageId,from:e.target.value,to})}/></label><label>Đến ngày<input type="date" value={to} onChange={e=>onChange({pageId,from,to:e.target.value})}/></label></div>;
}

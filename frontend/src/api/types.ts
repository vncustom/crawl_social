export type Admin = { username: string; role: string };
export type Job = { id: number; status: string; start_date: string; end_date: string };
export type FacebookPage = { id: number; page_id: string; display_name: string; enabled: boolean; daily_sync_enabled: boolean; latest_sync_at?: string | null; initial_job?: Job };
export type DailyInsight = { metric_date:string; daily_new_followers:number|null; followers_total:number|null; post_engagements:number|null; video_views:number|null; page_views:number|null };
export type PostRow = { external_post_id:string; created:string|null; message:string|null; media:string; reactions:number; comments:number; shares:number; engagement:number; permalink:string|null };
export type Report = { page_id:number; external_page_id:string; page_name:string; start_date:string; end_date:string; summary:{posts:number;reactions:number;comments:number;shares:number;total_engagement:number;average_engagement:number;current_followers:number|null;follower_growth:number|null};daily_posts:Array<{metric_date:string;posts:number;engagement:number}>;daily_insights:DailyInsight[];top_posts:PostRow[];latest_sync_at:string|null;active_job_id:number|null };

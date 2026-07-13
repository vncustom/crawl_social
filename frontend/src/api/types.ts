export type Admin = { username: string; role: string };
export type Job = { id: number; status: string; start_date: string; end_date: string };
export type FacebookPage = { id: number; page_id: string; display_name: string; enabled: boolean; daily_sync_enabled: boolean; latest_sync_at?: string | null; initial_job?: Job };

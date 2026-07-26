"""
fbcrawl_v2.py - Facebook Page Crawler (phien ban moi)

Thay doi so voi fbcrawl.py goc:
  - Them o nhap FB_PAGE_ID va FB_PAGE_ACCESS_TOKEN trong giao dien
    (neu de trong se load mac dinh tu os.getenv)
  - Bo tinh nang kiem tra deleted
  - Lay toan bo comment cua moi bai viet (co phan trang)
  - Bao cao CSV gom cac cot:
      FB_PAGE_ID | post_id | created_time | permalink_url
      message | full_picture | video_link | comments
"""

import csv
import json
import os
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from tkinter import Tk, StringVar, messagebox, ttk

import requests


# ──────────────────────────────────────────────
# Gia tri mac dinh tu bien moi truong
# ──────────────────────────────────────────────
DEFAULT_PAGE_ID = os.getenv("FB_PAGE_ID", "")
DEFAULT_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
GRAPH_VERSION = os.getenv("FB_GRAPH_VERSION", "v25.0")
DEFAULT_MAX_POSTS = int(os.getenv("FB_SYNC_MAX_POSTS", "500"))
DEFAULT_SLEEP_SECONDS = float(os.getenv("FB_SYNC_SLEEP_SECONDS", "1.5"))
DEFAULT_OUTPUT_DIR = Path("facebook_export")


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def configure_console_encoding():
    for stream in (sys.stdout, sys.stderr):
        encoding = (getattr(stream, "encoding", "") or "").lower()
        if encoding != "utf-8" and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def validate_date(value):
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(
            "Ngay khong hop le: {}. Dinh dang dung la YYYY-MM-DD.".format(value)
        ) from exc
    return value


def parse_datetime_value(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            parsed = datetime.strptime(value, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed
        except ValueError:
            pass
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed
    except ValueError:
        return None


def format_local_datetime(value):
    parsed = parse_datetime_value(value)
    if not parsed:
        return value or ""
    return parsed.astimezone().strftime("%d/%m/%Y %H:%M:%S")


# ──────────────────────────────────────────────
# Trich xuat video link
# ──────────────────────────────────────────────

def get_youtube_url(fb_url):
    if not fb_url:
        return ""
    youtube_url = fb_url
    if "facebook.com/l.php" in fb_url:
        match = re.search(r"[?&]u=([^&]+)", fb_url)
        if match:
            import urllib.parse
            youtube_url = urllib.parse.unquote(match.group(1))
    if any(d in youtube_url for d in ["youtube.com", "youtu.be"]):
        return youtube_url
    return ""


def extract_video_link(post):
    attachments = post.get("attachments", {}).get("data", [])
    for attachment in attachments:
        target_url = attachment.get("target", {}).get("url") or attachment.get("url", "")
        yt = get_youtube_url(target_url)
        if yt:
            return yt
        for sub in attachment.get("subattachments", {}).get("data", []):
            sub_url = sub.get("target", {}).get("url") or sub.get("url", "")
            yt = get_youtube_url(sub_url)
            if yt:
                return yt
        if attachment.get("type") in ("video_inline", "video_autoplay", "video"):
            fb_video_url = (
                attachment.get("target", {}).get("url")
                or attachment.get("url", "")
            )
            if fb_video_url:
                return fb_video_url
    return ""


# ──────────────────────────────────────────────
# Fetch comments (phan trang day du)
# ──────────────────────────────────────────────

def fetch_all_comments(post_id, access_token, sleep_seconds=0.3):
    url = "https://graph.facebook.com/{}/{}/comments".format(GRAPH_VERSION, post_id)
    params = {
        "access_token": access_token,
        "limit": 100,
        "fields": "id,from,message,created_time,like_count,comment_count",
        "filter": "stream",
        "summary": "false",
    }
    all_comments = []
    while url:
        try:
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException:
            break
        all_comments.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
        params = None
        if url and sleep_seconds:
            time.sleep(sleep_seconds)
    return all_comments


def format_comments(comments):
    lines = []
    for c in comments:
        author = c.get("from", {}).get("name", "")
        msg = c.get("message", "")
        ts = format_local_datetime(c.get("created_time", ""))
        lines.append("[{}] {}: {}".format(ts, author, msg))
    return "\n".join(lines)


# ──────────────────────────────────────────────
# Fetch posts
# ──────────────────────────────────────────────

@dataclass
class FetchResult:
    posts: list
    stopped_by_limit: bool = False
    stopped_at_post_id: str = ""
    stopped_at_created_time: str = ""
    page_requests: int = 0


def fetch_posts(
    since_date,
    until_date,
    page_id,
    access_token,
    max_posts=DEFAULT_MAX_POSTS,
    sleep_seconds=DEFAULT_SLEEP_SECONDS,
    progress_callback=None,
):
    validate_date(since_date)
    validate_date(until_date)

    url = "https://graph.facebook.com/{}/{}/posts".format(GRAPH_VERSION, page_id)
    params = {
        "access_token": access_token,
        "since": since_date,
        "until": until_date,
        "limit": 100,
        "fields": ",".join([
            "id",
            "message",
            "created_time",
            "permalink_url",
            "full_picture",
            "attachments{media,type,url,target,subattachments}",
        ]),
    }

    all_posts = []
    page_requests = 0
    stopped_by_limit = False
    stopped_at_post_id = ""
    stopped_at_created_time = ""

    while url:
        resp = requests.get(url, params=params, timeout=60)
        page_requests += 1
        resp.raise_for_status()
        data = resp.json()
        page_posts = data.get("data", [])
        remaining = max_posts - len(all_posts) if max_posts else len(page_posts)
        all_posts.extend(page_posts[:remaining])

        if progress_callback:
            progress_callback(len(all_posts), page_requests)

        next_url = data.get("paging", {}).get("next")
        if max_posts and next_url and len(all_posts) >= max_posts and len(page_posts) >= remaining:
            stopped_by_limit = True
            if all_posts:
                stopped_at_post_id = all_posts[-1].get("id", "")
                stopped_at_created_time = all_posts[-1].get("created_time", "")
            url = next_url
            break

        url = next_url
        params = None
        if url and sleep_seconds:
            time.sleep(sleep_seconds)

    return FetchResult(
        posts=all_posts,
        stopped_by_limit=stopped_by_limit,
        stopped_at_post_id=stopped_at_post_id,
        stopped_at_created_time=stopped_at_created_time,
        page_requests=page_requests,
    )


# ──────────────────────────────────────────────
# Crawl & Export
# ──────────────────────────────────────────────

@dataclass
class CrawlResult:
    rows: list = field(default_factory=list)
    csv_path: Path = field(default_factory=Path)
    json_path: Path = field(default_factory=Path)
    stopped_by_limit: bool = False
    stopped_at: str = ""
    page_requests: int = 0
    post_count: int = 0


def crawl_and_export(
    since_date,
    until_date,
    page_id,
    access_token,
    output_dir=DEFAULT_OUTPUT_DIR,
    max_posts=DEFAULT_MAX_POSTS,
    sleep_seconds=DEFAULT_SLEEP_SECONDS,
    progress_callback=None,
    comment_sleep_seconds=0.3,
):
    validate_date(since_date)
    validate_date(until_date)

    if not page_id:
        raise ValueError("FB_PAGE_ID khong duoc de trong.")
    if not access_token:
        raise ValueError("FB_PAGE_ACCESS_TOKEN khong duoc de trong.")

    # Buoc 1: lay danh sach bai viet
    fetch_result = fetch_posts(
        since_date=since_date,
        until_date=until_date,
        page_id=page_id,
        access_token=access_token,
        max_posts=max_posts,
        sleep_seconds=sleep_seconds,
        progress_callback=progress_callback,
    )

    rows = []
    total = len(fetch_result.posts)

    for idx, post in enumerate(fetch_result.posts):
        post_id = post.get("id", "")

        # Buoc 2: lay toan bo comment
        if progress_callback:
            progress_callback("comment {}/{}".format(idx + 1, total), fetch_result.page_requests)
        comments = fetch_all_comments(post_id, access_token, sleep_seconds=comment_sleep_seconds)
        comments_text = format_comments(comments)

        rows.append({
            "FB_PAGE_ID": page_id,
            "post_id": post_id,
            "created_time": format_local_datetime(post.get("created_time", "")),
            "permalink_url": post.get("permalink_url", ""),
            "message": post.get("message", ""),
            "full_picture": post.get("full_picture", ""),
            "video_link": extract_video_link(post),
            "comments": comments_text,
        })

    # Buoc 3: ghi file
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output_dir / "fb_report_{}_to_{}_{}.csv".format(since_date, until_date, timestamp)
    json_path = output_dir / "fb_report_{}_to_{}_{}.json".format(since_date, until_date, timestamp)

    fieldnames = [
        "FB_PAGE_ID", "post_id", "created_time", "permalink_url",
        "message", "full_picture", "video_link", "comments",
    ]

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    stopped_at = ""
    if fetch_result.stopped_by_limit:
        stopped_at = fetch_result.stopped_at_created_time or fetch_result.stopped_at_post_id

    return CrawlResult(
        rows=rows,
        csv_path=csv_path,
        json_path=json_path,
        stopped_by_limit=fetch_result.stopped_by_limit,
        stopped_at=stopped_at,
        page_requests=fetch_result.page_requests,
        post_count=len(rows),
    )


# ──────────────────────────────────────────────
# GUI - Tkinter
# ──────────────────────────────────────────────

def launch_gui():
    root = Tk()
    root.title("Facebook Page Crawler v2")
    root.geometry("750x590")
    root.resizable(False, False)

    page_id_var = StringVar(value=DEFAULT_PAGE_ID)
    token_var = StringVar(value=DEFAULT_ACCESS_TOKEN)
    since_var = StringVar(value=datetime.now().strftime("%Y-%m-01"))
    until_var = StringVar(value=datetime.now().strftime("%Y-%m-%d"))
    output_var = StringVar(value=str(DEFAULT_OUTPUT_DIR))
    max_posts_var = StringVar(value=str(DEFAULT_MAX_POSTS))
    status_var = StringVar(value="San sang.")

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)

    def add_row(parent, row, label, variable, show=None, width=56):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        kw = {"textvariable": variable, "width": width}
        if show:
            kw["show"] = show
        entry = ttk.Entry(parent, **kw)
        entry.grid(row=row, column=1, sticky="ew", pady=4)
        return entry

    # Cau hinh API
    api_frame = ttk.LabelFrame(frame, text="Cau hinh API", padding=10)
    api_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    add_row(api_frame, 0, "FB_PAGE_ID", page_id_var)
    token_entry = add_row(api_frame, 1, "FB_PAGE_ACCESS_TOKEN", token_var, show="*")

    show_token_state = [False]

    def toggle_token():
        show_token_state[0] = not show_token_state[0]
        token_entry.configure(show="" if show_token_state[0] else "*")
        toggle_btn.configure(text="An" if show_token_state[0] else "Hien")

    toggle_btn = ttk.Button(api_frame, text="Hien", command=toggle_token, width=6)
    toggle_btn.grid(row=1, column=2, padx=(4, 0))

    ttk.Label(api_frame, text="(De trong se dung os.getenv)", foreground="gray").grid(
        row=2, column=0, columnspan=3, sticky="w", pady=(0, 2)
    )

    # Khoang thoi gian
    date_frame = ttk.LabelFrame(frame, text="Khoang thoi gian crawl", padding=10)
    date_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
    add_row(date_frame, 0, "Tu ngay (YYYY-MM-DD)", since_var)
    add_row(date_frame, 1, "Den ngay (YYYY-MM-DD)", until_var)

    # Cai dat
    adv_frame = ttk.LabelFrame(frame, text="Cai dat xuat file", padding=10)
    adv_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
    add_row(adv_frame, 0, "Thu muc xuat file", output_var)
    add_row(adv_frame, 1, "So bai toi da", max_posts_var, width=10)

    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=3, column=0, pady=10)

    progress = ttk.Progressbar(frame, mode="indeterminate")
    progress.grid(row=4, column=0, sticky="ew", pady=(0, 6))

    ttk.Label(frame, textvariable=status_var, wraplength=710, justify="left").grid(
        row=5, column=0, sticky="w"
    )

    buttons = []

    def set_busy(is_busy):
        for btn in buttons:
            btn.configure(state="disabled" if is_busy else "normal")
        if is_busy:
            progress.start(12)
        else:
            progress.stop()

    def resolve_credentials():
        pid = page_id_var.get().strip() or os.getenv("FB_PAGE_ID", "").strip()
        tok = token_var.get().strip() or os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()
        return pid, tok

    def run_crawl():
        def progress_callback(info, page_req):
            if isinstance(info, int):
                msg = "Dang lay bai... da co {} bai, {} request.".format(info, page_req)
            else:
                msg = "Dang lay {} ...".format(info)
            root.after(0, lambda: status_var.set(msg))

        def worker():
            try:
                pid, tok = resolve_credentials()
                try:
                    max_p = int(max_posts_var.get().strip() or DEFAULT_MAX_POSTS)
                except ValueError:
                    max_p = DEFAULT_MAX_POSTS

                result = crawl_and_export(
                    since_date=since_var.get().strip(),
                    until_date=until_var.get().strip(),
                    page_id=pid,
                    access_token=tok,
                    output_dir=Path(output_var.get().strip() or str(DEFAULT_OUTPUT_DIR)),
                    max_posts=max_p,
                    progress_callback=progress_callback,
                )

                lines = [
                    "Hoan tat! Da crawl {} bai, {} request.".format(
                        result.post_count, result.page_requests
                    ),
                    "CSV: {}".format(result.csv_path.resolve()),
                    "JSON: {}".format(result.json_path.resolve()),
                ]
                if result.stopped_by_limit:
                    lines.append(
                        "Dat gioi han {} bai, dung o: {}."
                        " Hay chia nho khoang ngay de lay het.".format(
                            max_p, result.stopped_at or "khong ro"
                        )
                    )

                msg = "\n".join(lines)
                root.after(0, lambda: status_var.set(lines[0]))
                root.after(0, lambda: messagebox.showinfo("Hoan tat", msg))
            except Exception as exc:
                err = str(exc)
                root.after(0, lambda: status_var.set("Loi: {}".format(err)))
                root.after(0, lambda: messagebox.showerror("Loi", err))
            finally:
                root.after(0, lambda: set_busy(False))

        set_busy(True)
        status_var.set("Dang chay, vui long doi...")
        threading.Thread(target=worker, daemon=True).start()

    crawl_btn = ttk.Button(btn_frame, text="Crawl & Xuat bao cao", command=run_crawl)
    crawl_btn.pack(side="left", padx=6)
    buttons.append(crawl_btn)

    frame.columnconfigure(0, weight=1)
    for child in (api_frame, date_frame, adv_frame):
        child.columnconfigure(1, weight=1)

    root.mainloop()


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    configure_console_encoding()
    launch_gui()

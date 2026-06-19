import argparse
import csv
import json
import os
import re
import sqlite3
import sys
import threading
import time
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from tkinter import Tk, StringVar, messagebox, ttk

import requests


PAGE_ID = os.getenv("FB_PAGE_ID", "1125132200689307")
GRAPH_VERSION = os.getenv("FB_GRAPH_VERSION", "v25.0")
DEFAULT_DB_PATH = Path("facebook_archive") / "facebook_audit.db"
DEFAULT_MAX_SYNC_POSTS = int(os.getenv("FB_SYNC_MAX_POSTS", "500"))
DEFAULT_MAX_CHECK_POSTS = int(os.getenv("FB_CHECK_MAX_POSTS", "500"))
DEFAULT_SYNC_SLEEP_SECONDS = float(os.getenv("FB_SYNC_SLEEP_SECONDS", "1.5"))
DEFAULT_CHECK_SLEEP_SECONDS = float(os.getenv("FB_CHECK_SLEEP_SECONDS", "0.5"))


@dataclass
class FetchResult:
    posts: list
    stopped_by_limit: bool = False
    stopped_at_post_id: str = ""
    stopped_at_created_time: str = ""
    next_page_url: str = ""
    page_requests: int = 0


@dataclass
class SyncResult:
    synced_count: int
    deleted_by_snapshot: list = field(default_factory=list)
    stopped_by_limit: bool = False
    stopped_at_post_id: str = ""
    stopped_at_created_time: str = ""
    next_page_url: str = ""
    page_requests: int = 0


def get_access_token():
    token = os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Thieu bien moi truong FB_PAGE_ACCESS_TOKEN.")
    return token


def validate_date(value):
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Ngay khong hop le: {value}. Dinh dang dung la YYYY-MM-DD.") from exc
    return value


def now_utc_iso():
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_posts_since_until(
    since_date,
    until_date,
    page_id=PAGE_ID,
    access_token=None,
    max_posts=DEFAULT_MAX_SYNC_POSTS,
    sleep_seconds=DEFAULT_SYNC_SLEEP_SECONDS,
    progress_callback=None,
):
    validate_date(since_date)
    validate_date(until_date)
    token = access_token or get_access_token()
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{page_id}/posts"
    params = {
        "access_token": token,
        "since": since_date,
        "until": until_date,
        "limit": 100,
        "fields": ",".join(
            [
                "id",
                "message",
                "created_time",
                "permalink_url",
                "full_picture",
                "attachments{media,type,url,target,subattachments}",
                "comments.summary(true).limit(0)",
                "reactions.summary(true).limit(0)",
                "shares",
            ]
        ),
    }
    all_posts = []

    page_requests = 0
    stopped_by_limit = False
    stopped_at_post_id = ""
    stopped_at_created_time = ""

    while url:
        response = requests.get(url, params=params, timeout=60)
        page_requests += 1
        response.raise_for_status()
        data = response.json()
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
        next_page_url=url or "",
        page_requests=page_requests,
    )


def fetch_post(post_id, access_token=None):
    token = access_token or get_access_token()
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{post_id}"
    params = {
        "access_token": token,
        "fields": "id,created_time,message,permalink_url,updated_time,is_published",
    }
    response = requests.get(url, params=params, timeout=30)
    if response.status_code == 400:
        body = response.json()
        code = body.get("error", {}).get("code")
        message = body.get("error", {}).get("message", "")
        if code in {100, 803} or "does not exist" in message.lower():
            return None
    response.raise_for_status()
    return response.json()


def graph_post_exists(post_id):
    return fetch_post(post_id) is not None


def get_count(post, key):
    return post.get(key, {}).get("summary", {}).get("total_count", 0)


def get_youtube_video_info(fb_url):
    if not fb_url:
        return "", ""

    youtube_url = fb_url
    if "facebook.com/l.php" in fb_url:
        match = re.search(r"[?&]u=([^&]+)", fb_url)
        if match:
            import urllib.parse

            youtube_url = urllib.parse.unquote(match.group(1))

    if not any(domain in youtube_url for domain in ["youtube.com", "youtu.be"]):
        return "", ""

    try:
        oembed_url = f"https://www.youtube.com/oembed?url={youtube_url}&format=json"
        response = requests.get(oembed_url, timeout=10)
        if response.status_code == 200:
            video_data = response.json()
            return youtube_url, video_data.get("title", "")
    except requests.RequestException:
        pass

    return youtube_url, ""


def extract_youtube_link(post):
    attachments = post.get("attachments", {}).get("data", [])
    for attachment in attachments:
        target_url = attachment.get("target", {}).get("url") or attachment.get("url")
        if target_url:
            video_url, video_title = get_youtube_video_info(target_url)
            if video_url:
                return video_url, video_title

        for sub_attachment in attachment.get("subattachments", {}).get("data", []):
            sub_target_url = sub_attachment.get("target", {}).get("url") or sub_attachment.get("url")
            if sub_target_url:
                video_url, video_title = get_youtube_video_info(sub_target_url)
                if video_url:
                    return video_url, video_title

    return "", ""


def init_db(db_path=DEFAULT_DB_PATH):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            """
            create table if not exists posts (
                post_id text primary key,
                created_time text,
                first_seen_at text not null,
                last_seen_at text not null,
                status text not null,
                message text,
                permalink_url text,
                full_picture text,
                youtube_video_url text,
                youtube_video_title text,
                last_checked_at text,
                deleted_detected_at text
            )
            """
        )
        conn.execute(
            """
            create table if not exists post_snapshots (
                id integer primary key autoincrement,
                post_id text not null,
                crawled_at text not null,
                since_date text not null,
                until_date text not null,
                message text,
                permalink_url text,
                full_picture text,
                reaction_count integer not null,
                comment_count integer not null,
                share_count integer not null,
                raw_json text not null
            )
            """
        )
        conn.commit()
        conn.execute(
            """
            create table if not exists deletion_events (
                id integer primary key autoincrement,
                post_id text not null,
                detected_at text not null,
                source text not null,
                note text
            )
            """
        )
        conn.commit()
    return db_path


def prepare_post_for_storage(post):
    post = dict(post)
    video_url, video_title = extract_youtube_link(post)
    post["youtube_video_url"] = video_url
    post["youtube_video_title"] = video_title
    return post


def normalize_fetch_result(value):
    if isinstance(value, FetchResult):
        return value
    return FetchResult(posts=value)


def mark_missing_posts_from_sync(conn, since_date, until_date, seen_post_ids, checked_at):
    if not seen_post_ids:
        placeholders = "''"
        params = [since_date, until_date]
    else:
        placeholders = ",".join("?" for _ in seen_post_ids)
        params = [since_date, until_date, *seen_post_ids]

    rows = conn.execute(
        f"""
        select post_id
        from posts
        where status != 'suspected_deleted'
          and created_time >= ?
          and created_time < ?
          and post_id not in ({placeholders})
        order by created_time
        """,
        params,
    ).fetchall()
    deleted = []
    for (post_id,) in rows:
        conn.execute(
            """
            update posts
            set status = 'suspected_deleted',
                last_checked_at = ?,
                deleted_detected_at = ?
            where post_id = ? and status != 'suspected_deleted'
            """,
            (checked_at, checked_at, post_id),
        )
        conn.execute(
            """
            insert into deletion_events (post_id, detected_at, source, note)
            values (?, ?, 'sync_snapshot', 'Bai da tung co trong khoang ngay nhung khong xuat hien trong lan sync day du moi')
            """,
            (post_id, checked_at),
        )
        deleted.append(post_id)
    return deleted


def sync_posts(
    db_path=DEFAULT_DB_PATH,
    since_date=None,
    until_date=None,
    fetcher=None,
    max_posts=DEFAULT_MAX_SYNC_POSTS,
    sleep_seconds=DEFAULT_SYNC_SLEEP_SECONDS,
    progress_callback=None,
):
    if not since_date or not until_date:
        raise ValueError("Can nhap since_date va until_date.")
    validate_date(since_date)
    validate_date(until_date)
    fetcher = fetcher or fetch_posts_since_until
    db_path = init_db(db_path)
    crawled_at = now_utc_iso()
    try:
        fetch_value = fetcher(
            since_date,
            until_date,
            max_posts=max_posts,
            sleep_seconds=sleep_seconds,
            progress_callback=progress_callback,
        )
    except TypeError:
        fetch_value = fetcher(since_date, until_date)
    fetch_result = normalize_fetch_result(fetch_value)
    posts = [prepare_post_for_storage(post) for post in fetch_result.posts]
    seen_post_ids = [post.get("id", "") for post in posts if post.get("id")]
    deleted_by_snapshot = []

    with closing(sqlite3.connect(db_path)) as conn:
        for post in posts:
            conn.execute(
                """
                insert into posts (
                    post_id, created_time, first_seen_at, last_seen_at, status,
                    message, permalink_url, full_picture, youtube_video_url, youtube_video_title
                )
                values (?, ?, ?, ?, 'active', ?, ?, ?, ?, ?)
                on conflict(post_id) do update set
                    last_seen_at = excluded.last_seen_at,
                    status = 'active',
                    message = excluded.message,
                    permalink_url = excluded.permalink_url,
                    full_picture = excluded.full_picture,
                    youtube_video_url = excluded.youtube_video_url,
                    youtube_video_title = excluded.youtube_video_title
                """,
                (
                    post.get("id", ""),
                    post.get("created_time", ""),
                    crawled_at,
                    crawled_at,
                    post.get("message", ""),
                    post.get("permalink_url", ""),
                    post.get("full_picture", ""),
                    post.get("youtube_video_url", ""),
                    post.get("youtube_video_title", ""),
                ),
            )
            conn.execute(
                """
                insert into post_snapshots (
                    post_id, crawled_at, since_date, until_date, message, permalink_url,
                    full_picture, reaction_count, comment_count, share_count, raw_json
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    post.get("id", ""),
                    crawled_at,
                    since_date,
                    until_date,
                    post.get("message", ""),
                    post.get("permalink_url", ""),
                    post.get("full_picture", ""),
                    get_count(post, "reactions"),
                    get_count(post, "comments"),
                    post.get("shares", {}).get("count", 0),
                    json.dumps(post, ensure_ascii=False),
                ),
            )
        if not fetch_result.stopped_by_limit:
            deleted_by_snapshot = mark_missing_posts_from_sync(
                conn,
                since_date,
                until_date,
                seen_post_ids,
                crawled_at,
            )
        conn.commit()
    return SyncResult(
        synced_count=len(posts),
        deleted_by_snapshot=deleted_by_snapshot,
        stopped_by_limit=fetch_result.stopped_by_limit,
        stopped_at_post_id=fetch_result.stopped_at_post_id,
        stopped_at_created_time=fetch_result.stopped_at_created_time,
        next_page_url=fetch_result.next_page_url,
        page_requests=fetch_result.page_requests,
    )


def check_deleted_posts(
    db_path=DEFAULT_DB_PATH,
    post_checker=None,
    max_checks=DEFAULT_MAX_CHECK_POSTS,
    sleep_seconds=DEFAULT_CHECK_SLEEP_SECONDS,
):
    post_checker = post_checker or graph_post_exists
    db_path = init_db(db_path)
    checked_at = now_utc_iso()
    deleted = []

    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute(
            """
            select post_id
            from posts
            where status != 'suspected_deleted'
            order by coalesce(last_checked_at, ''), created_time
            limit ?
            """,
            (max_checks,),
        ).fetchall()
        for index, (post_id,) in enumerate(rows):
            exists = post_checker(post_id)
            conn.execute(
                "update posts set last_checked_at = ? where post_id = ?",
                (checked_at, post_id),
            )
            if exists:
                continue
            conn.execute(
                """
                update posts
                set status = 'suspected_deleted', deleted_detected_at = ?
                where post_id = ? and status != 'suspected_deleted'
                """,
                (checked_at, post_id),
            )
            if conn.total_changes:
                conn.execute(
                    """
                    insert into deletion_events (post_id, detected_at, source, note)
                    values (?, ?, 'polling', 'Graph API khong con tra ve bai viet')
                    """,
                    (post_id, checked_at),
                )
                deleted.append(post_id)
            if sleep_seconds and index < len(rows) - 1:
                time.sleep(sleep_seconds)
        conn.commit()

    return deleted


def export_report(db_path=DEFAULT_DB_PATH, csv_path=None):
    db_path = init_db(db_path)
    csv_path = Path(csv_path or Path("facebook_archive") / "audit_report.csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "post_id",
        "status",
        "created_time",
        "first_seen_at",
        "last_seen_at",
        "last_checked_at",
        "deleted_detected_at",
        "message",
        "permalink_url",
        "full_picture",
        "youtube_video_url",
        "youtube_video_title",
    ]

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            select post_id, status, created_time, first_seen_at, last_seen_at,
                   last_checked_at, deleted_detected_at, message, permalink_url,
                   full_picture, youtube_video_url, youtube_video_title
            from posts
            order by created_time desc, first_seen_at desc
            """
        ).fetchall()

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(dict(row) for row in rows)

    return len(rows)


def save_posts(posts, since_date, until_date):
    base_folder = Path("facebook_archive")
    archive_folder = base_folder / f"{since_date}_to_{until_date}"
    archive_folder.mkdir(parents=True, exist_ok=True)
    json_file = archive_folder / "posts.json"
    csv_file = archive_folder / "posts.csv"
    posts = [prepare_post_for_storage(post) for post in posts]

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

    with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "post_id",
                "created_time",
                "message",
                "permalink_url",
                "full_picture",
                "reaction_count",
                "comment_count",
                "share_count",
                "youtube_video_url",
                "youtube_video_title",
            ]
        )
        for post in posts:
            writer.writerow(
                [
                    post.get("id", ""),
                    post.get("created_time", ""),
                    post.get("message", ""),
                    post.get("permalink_url", ""),
                    post.get("full_picture", ""),
                    get_count(post, "reactions"),
                    get_count(post, "comments"),
                    post.get("shares", {}).get("count", 0),
                    post.get("youtube_video_url", ""),
                    post.get("youtube_video_title", ""),
                ]
            )

    return archive_folder, json_file, csv_file


def build_parser():
    parser = argparse.ArgumentParser(description="Facebook Page crawler va audit bai bi xoa.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Duong dan SQLite database.")
    subparsers = parser.add_subparsers(dest="command")

    sync_parser = subparsers.add_parser("sync", help="Crawl bai moi va cap nhat snapshot.")
    sync_parser.add_argument("--since", required=True, help="Ngay bat dau YYYY-MM-DD.")
    sync_parser.add_argument("--until", required=True, help="Ngay ket thuc YYYY-MM-DD.")

    subparsers.add_parser("check-deleted", help="Kiem tra cac bai da biet con ton tai khong.")

    report_parser = subparsers.add_parser("report", help="Xuat CSV audit.")
    report_parser.add_argument("--out", default=str(Path("facebook_archive") / "audit_report.csv"))

    subparsers.add_parser("gui", help="Mo giao dien Tkinter.")
    return parser


def run_cli(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        launch_gui()
        return 0

    try:
        if args.command == "sync":
            result = sync_posts(args.db, args.since, args.until)
            print(f"Da sync {result.synced_count} bai vao {Path(args.db).resolve()}")
            print(f"So request phan trang: {result.page_requests}")
            if result.deleted_by_snapshot:
                print(f"Tu snapshot sync, phat hien {len(result.deleted_by_snapshot)} bai nghi da xoa:")
                for post_id in result.deleted_by_snapshot:
                    print(post_id)
            if result.stopped_by_limit:
                stop_text = result.stopped_at_created_time or result.stopped_at_post_id or "khong ro"
                print(
                    "Da dat gioi han 500 bai nen dung de tranh goi API qua nhieu. "
                    f"Dang dung o: {stop_text}. Hay sync tiep vao ngay mai hoac chia nho khoang ngay."
                )
        elif args.command == "check-deleted":
            deleted = check_deleted_posts(args.db)
            print(f"Phat hien {len(deleted)} bai nghi da xoa")
            for post_id in deleted:
                print(post_id)
        elif args.command == "report":
            count = export_report(args.db, args.out)
            print(f"Da xuat {count} dong audit ra {Path(args.out).resolve()}")
        elif args.command == "gui":
            launch_gui(args.db)
    except Exception as exc:
        print(f"Loi: {exc}", file=sys.stderr)
        return 1
    return 0


def launch_gui(default_db=DEFAULT_DB_PATH):
    root = Tk()
    root.title("Facebook Page Audit")
    root.geometry("620x310")
    root.resizable(False, False)

    db_var = StringVar(value=str(default_db))
    since_var = StringVar(value=datetime.now().strftime("%Y-%m-01"))
    until_var = StringVar(value=datetime.now().strftime("%Y-%m-%d"))
    report_var = StringVar(value=str(Path("facebook_archive") / "audit_report.csv"))
    status_var = StringVar(value="San sang.")

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)

    def add_row(row, label, variable):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=5)
        entry = ttk.Entry(frame, textvariable=variable, width=54)
        entry.grid(row=row, column=1, sticky="ew", pady=5)
        return entry

    add_row(0, "SQLite DB", db_var)
    add_row(1, "Tu ngay", since_var)
    add_row(2, "Den ngay", until_var)
    add_row(3, "File report", report_var)

    button_frame = ttk.Frame(frame)
    button_frame.grid(row=4, column=0, columnspan=2, pady=14)
    buttons = []

    progress = ttk.Progressbar(frame, mode="indeterminate")
    progress.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 10))

    def set_busy(is_busy):
        for button in buttons:
            button.configure(state="disabled" if is_busy else "normal")
        if is_busy:
            progress.start(12)
        else:
            progress.stop()

    def format_sync_message(result):
        lines = [
            f"Da sync {result.synced_count} bai.",
            f"So request phan trang: {result.page_requests}.",
        ]
        if result.deleted_by_snapshot:
            lines.append(f"Snapshot phat hien {len(result.deleted_by_snapshot)} bai nghi da xoa.")
        if result.stopped_by_limit:
            stop_text = result.stopped_at_created_time or result.stopped_at_post_id or "khong ro"
            lines.append(
                "Da dat gioi han 500 bai nen tam dung de giam rui ro rate limit. "
                f"Dang dung o: {stop_text}. Ngay mai hay sync tiep hoac chia nho khoang ngay."
            )
        return "\n".join(lines)

    def run_action(action):
        def progress_callback(count, page_requests):
            root.after(
                0,
                lambda: status_var.set(
                    f"Dang sync... da lay {count}/500 bai, {page_requests} request."
                ),
            )

        def worker():
            try:
                if action == "sync":
                    result = sync_posts(
                        db_var.get(),
                        since_var.get(),
                        until_var.get(),
                        progress_callback=progress_callback,
                    )
                    message = format_sync_message(result)
                elif action == "check":
                    deleted = check_deleted_posts(db_var.get())
                    message = f"Phat hien {len(deleted)} bai nghi da xoa."
                else:
                    count = export_report(db_var.get(), report_var.get())
                    message = f"Da xuat {count} dong report."

                root.after(0, lambda: status_var.set(message.splitlines()[0]))
                root.after(0, lambda: messagebox.showinfo("Hoan tat", message))
            except Exception as exc:
                error_message = str(exc)
                root.after(0, lambda: status_var.set(f"Loi: {error_message}"))
                root.after(0, lambda: messagebox.showerror("Loi", error_message))
            finally:
                root.after(0, lambda: set_busy(False))

        set_busy(True)
        status_var.set("Dang chay, vui long doi...")
        threading.Thread(target=worker, daemon=True).start()

    buttons.append(ttk.Button(button_frame, text="Sync", command=lambda: run_action("sync")))
    buttons.append(ttk.Button(button_frame, text="Check Deleted", command=lambda: run_action("check")))
    buttons.append(ttk.Button(button_frame, text="Export Report", command=lambda: run_action("report")))
    for button in buttons:
        button.pack(side="left", padx=6)

    ttk.Label(frame, textvariable=status_var, wraplength=580).grid(row=6, column=0, columnspan=2, sticky="w")
    frame.columnconfigure(1, weight=1)
    root.mainloop()


if __name__ == "__main__":
    raise SystemExit(run_cli())

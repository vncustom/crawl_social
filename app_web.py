"""
app_web.py - Web Dashboard Server cho Facebook Page Crawler (Có Quản trị Admin)

Sử dụng FastAPI + Uvicorn kết hợp giao diện Web SPA trực quan.
 - Tích hợp Đăng nhập Admin (user: admin, password: admin).
 - Quản lý danh sách FB_PAGE_ID và FB_PAGE_ACCESS_TOKEN lưu tự động vào .env.
 - Người dùng bình thường chỉ chọn Page ID từ Dropdown menu, không cần nhập Token.
"""

import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# Import core logic từ fbcrawl_v2
from fbcrawl_v2 import (
    DEFAULT_ACCESS_TOKEN,
    DEFAULT_MAX_POSTS,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PAGE_ID,
    extract_video_link,
    fetch_all_comments,
    fetch_posts,
    format_comments,
    format_local_datetime,
    validate_date,
)

app = FastAPI(title="Facebook Page Crawler Web Dashboard")

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
TEMPLATES_DIR.mkdir(exist_ok=True)
ENV_FILE = BASE_DIR / ".env"

ADMIN_TOKEN = "admin_session_token_888"


# ──────────────────────────────────────────────
# Helper Đọc / Ghi cấu hình Page vào .env
# ──────────────────────────────────────────────

def load_pages_from_env() -> list[dict]:
    pages = []
    # 1. Đọc từ env variable FB_PAGES_CONFIG
    raw_config = os.getenv("FB_PAGES_CONFIG", "").strip()
    if raw_config:
        try:
            pages = json.loads(raw_config)
        except Exception:
            pass

    # 2. Nếu trống, đọc trực tiếp từ file .env
    if not pages and ENV_FILE.exists():
        try:
            content = ENV_FILE.read_text(encoding="utf-8")
            for line in content.splitlines():
                if line.startswith("FB_PAGES_CONFIG="):
                    val = line.split("=", 1)[1].strip().strip("'\"")
                    try:
                        pages = json.loads(val)
                    except Exception:
                        pass
        except Exception:
            pass

    # 3. Mặc định nếu vẫn trống: lấy từ FB_PAGE_ID & FB_PAGE_ACCESS_TOKEN
    if not pages:
        pid = os.getenv("FB_PAGE_ID", DEFAULT_PAGE_ID)
        tok = os.getenv("FB_PAGE_ACCESS_TOKEN", DEFAULT_ACCESS_TOKEN)
        if pid:
            pages = [{
                "page_id": pid,
                "name": f"Page Mặc Định ({pid})",
                "access_token": tok,
            }]
    return pages


def save_pages_to_env(pages: list[dict]):
    config_json = json.dumps(pages, ensure_ascii=False)
    env_lines = []
    if ENV_FILE.exists():
        try:
            env_lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
        except Exception:
            env_lines = []

    updated_config = False
    updated_pid = False
    updated_tok = False

    first_pid = pages[0]["page_id"] if pages else ""
    first_tok = pages[0]["access_token"] if pages else ""

    new_lines = []
    for line in env_lines:
        if line.startswith("FB_PAGES_CONFIG="):
            new_lines.append(f"FB_PAGES_CONFIG='{config_json}'")
            updated_config = True
        elif line.startswith("FB_PAGE_ID="):
            new_lines.append(f"FB_PAGE_ID={first_pid}")
            updated_pid = True
        elif line.startswith("FB_PAGE_ACCESS_TOKEN="):
            new_lines.append(f"FB_PAGE_ACCESS_TOKEN={first_tok}")
            updated_tok = True
        else:
            new_lines.append(line)

    if not updated_config:
        new_lines.append(f"FB_PAGES_CONFIG='{config_json}'")
    if not updated_pid and first_pid:
        new_lines.append(f"FB_PAGE_ID={first_pid}")
    if not updated_tok and first_tok:
        new_lines.append(f"FB_PAGE_ACCESS_TOKEN={first_tok}")

    ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # Cập nhật os.environ trong bộ nhớ process hiện tại
    os.environ["FB_PAGES_CONFIG"] = config_json
    if first_pid:
        os.environ["FB_PAGE_ID"] = first_pid
    if first_tok:
        os.environ["FB_PAGE_ACCESS_TOKEN"] = first_tok


def check_admin(request: Request):
    auth_header = request.headers.get("Authorization", "")
    token_header = request.headers.get("X-Admin-Token", "")
    if ADMIN_TOKEN in auth_header or token_header == ADMIN_TOKEN:
        return True
    raise HTTPException(status_code=403, detail="Yêu cầu quyền Quản trị viên (Admin).")


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Phục vụ trang Web Dashboard chính."""
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Giao diện index.html không tồn tại.")
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))


@app.post("/api/login")
async def login_api(request: Request):
    """Đăng nhập Admin (user: admin, password: admin)."""
    body = await request.json()
    username = (body.get("username") or "").strip()
    password = (body.get("password") or "").strip()
    if username == "admin" and password == "admin":
        return {
            "status": "success",
            "token": ADMIN_TOKEN,
            "username": "admin",
            "message": "Đăng nhập Admin thành công!",
        }
    raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu không chính xác.")


@app.get("/api/pages")
async def get_public_pages():
    """Trả về danh sách các Page công khai (ẨN Access Token cho người dùng thường)."""
    pages = load_pages_from_env()
    return [
        {
            "page_id": p.get("page_id", ""),
            "name": p.get("name", p.get("page_id", "")),
        }
        for p in pages
    ]


@app.get("/api/admin/pages")
async def get_admin_pages(request: Request):
    """Trả về danh sách Page đầy đủ kèm Token (Chỉ dành cho Admin)."""
    check_admin(request)
    return load_pages_from_env()


@app.post("/api/admin/pages")
async def save_admin_pages(request: Request):
    """Thêm hoặc lưu danh sách Page và ghi tự động vào file .env (Dành cho Admin)."""
    check_admin(request)
    body = await request.json()

    # Nếu gửi nguyên danh sách
    if "pages" in body and isinstance(body["pages"], list):
        pages = body["pages"]
    else:
        # Nếu gửi 1 page lẻ
        pid = (body.get("page_id") or "").strip()
        tok = (body.get("access_token") or "").strip()
        name = (body.get("name") or f"Page {pid}").strip()
        if not pid or not tok:
            raise HTTPException(status_code=400, detail="Thiếu FB_PAGE_ID hoặc FB_PAGE_ACCESS_TOKEN.")
        
        pages = load_pages_from_env()
        # Cập nhật nếu đã tồn tại, hoặc thêm mới
        found = False
        for p in pages:
            if p["page_id"] == pid:
                p["name"] = name
                p["access_token"] = tok
                found = True
                break
        if not found:
            pages.append({"page_id": pid, "name": name, "access_token": tok})

    save_pages_to_env(pages)
    return {"status": "success", "message": "Đã lưu cấu hình Page vào file .env!", "pages": pages}


@app.delete("/api/admin/pages/{page_id}")
async def delete_admin_page(page_id: str, request: Request):
    """Xóa Page theo Page ID và cập nhật file .env (Dành cho Admin)."""
    check_admin(request)
    pages = load_pages_from_env()
    new_pages = [p for p in pages if p["page_id"] != page_id]
    if len(new_pages) == len(pages):
        raise HTTPException(status_code=404, detail="Không tìm thấy Page ID.")
    save_pages_to_env(new_pages)
    return {"status": "success", "message": f"Đã xóa Page {page_id} khỏi cấu hình .env."}


@app.get("/api/config")
async def get_default_config():
    """Trả về thông số mặc định cho UI."""
    pages = load_pages_from_env()
    pid = pages[0]["page_id"] if pages else os.getenv("FB_PAGE_ID", DEFAULT_PAGE_ID)
    return {
        "page_id": pid,
        "max_posts": int(os.getenv("FB_SYNC_MAX_POSTS", DEFAULT_MAX_POSTS)),
        "default_since": datetime.now().strftime("%Y-%m-01"),
        "default_until": datetime.now().strftime("%Y-%m-%d"),
        "configured_pages_count": len(pages),
    }


def resolve_token_for_page(page_id: str, provided_token: str = "") -> str:
    """Tra cứu token tương ứng với page_id từ cấu hình .env."""
    if provided_token and provided_token.strip():
        return provided_token.strip()
    pages = load_pages_from_env()
    for p in pages:
        if p.get("page_id") == page_id:
            return p.get("access_token", "")
    return os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()


@app.post("/api/crawl")
async def crawl_api(request: Request):
    """Endpoint REST crawl bài viết & comment."""
    body = await request.json()
    page_id = (body.get("page_id") or "").strip()
    access_token = resolve_token_for_page(page_id, body.get("access_token", ""))
    since_date = (body.get("since_date") or "").strip()
    until_date = (body.get("until_date") or "").strip()
    max_posts = int(body.get("max_posts") or DEFAULT_MAX_POSTS)

    if not page_id:
        raise HTTPException(status_code=400, detail="Thiếu FB_PAGE_ID.")
    if not access_token:
        raise HTTPException(
            status_code=400,
            detail=f"Không tìm thấy FB_PAGE_ACCESS_TOKEN cho Page ID {page_id}. Vui lòng liên hệ Admin cấu hình."
        )

    try:
        validate_date(since_date)
        validate_date(until_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        fetch_result = fetch_posts(
            since_date=since_date,
            until_date=until_date,
            page_id=page_id,
            access_token=access_token,
            max_posts=max_posts,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi khi gọi Facebook API: {exc}")

    posts_output = []
    total = len(fetch_result.posts)
    video_count = 0
    image_count = 0
    total_comments_count = 0

    for idx, post in enumerate(fetch_result.posts):
        post_id = post.get("id", "")
        comments_raw = fetch_all_comments(post_id, access_token)
        comments_text = format_comments(comments_raw)
        total_comments_count += len(comments_raw)

        video_link = extract_video_link(post)
        full_picture = post.get("full_picture", "")

        if video_link:
            video_count += 1
        if full_picture:
            image_count += 1

        formatted_comments_list = []
        for c in comments_raw:
            formatted_comments_list.append({
                "id": c.get("id", ""),
                "author": c.get("from", {}).get("name", "Người dùng Facebook"),
                "message": c.get("message", ""),
                "created_time": format_local_datetime(c.get("created_time", "")),
                "like_count": c.get("like_count", 0),
            })

        posts_output.append({
            "FB_PAGE_ID": page_id,
            "post_id": post_id,
            "created_time": format_local_datetime(post.get("created_time", "")),
            "permalink_url": post.get("permalink_url", ""),
            "message": post.get("message", ""),
            "full_picture": full_picture,
            "video_link": video_link,
            "comments_text": comments_text,
            "comments_list": formatted_comments_list,
            "comment_count": len(comments_raw),
        })

    return {
        "status": "success",
        "page_id": page_id,
        "since_date": since_date,
        "until_date": until_date,
        "stats": {
            "total_posts": total,
            "total_comments": total_comments_count,
            "video_posts": video_count,
            "image_posts": image_count,
            "page_requests": fetch_result.page_requests,
            "stopped_by_limit": fetch_result.stopped_by_limit,
            "stopped_at": fetch_result.stopped_at_created_time or fetch_result.stopped_at_post_id,
        },
        "posts": posts_output,
    }


def start():
    """Khởi chạy web server."""
    port = int(os.getenv("PORT", "8000"))
    print(f"🚀 Dashboard Web đang chạy tại: http://localhost:{port}")
    uvicorn.run("app_web:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    start()
